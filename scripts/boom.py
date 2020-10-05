import sys
import os
import asyncio
import random
import time
import concurrent.futures
import datetime


from writers_v1 import SMDR_SQL
from smdrconfig_v1 import Configuration
from smdr_v1 import *
from enum import Enum
from config import SMDR_CONFIG_NAME


config = Configuration(SMDR_CONFIG_NAME)


#--------------------------------------
def debug(*value):
	if( config.get('main','debug').lower() == 'true' and value[0] != 'service' ):
		fd = None
		try:
			fd = open('c:\\debug.log','a+')
			str = ''
			for i in value:
				str = str+'{0}'.format(i)
			fd.write(str+'\n')
			fd.close()
		except OSError:
			if(fd):
				fd.close()
		except IOError as e:
			print(os.strerror(e))
		print(*value)
#	if( config.get('main','service').lower() == 'true' and value[0] == 'service' ):
#		fd = None
#		try:
#			fd = open('c:\\service.log','a+')
#			str = ''
#			for i in value:
#				str = str+'{0}'.format(i)
#			fd.write(str+'\n')
#			fd.close()
#		except OSError:
#			if(fd):
#				fd.close()
#		print(*value)
#--------------------------------------


class STATE(Enum):
	EMPTY  = -1
	REQ    = 0    # send request
	READ   = 1    # read from server 
	PARSE  = 2	  # parse data from server
	WRITE  = 3    # write to server
	ERROR  = 4    # parse error
	ACK    = 5	  # ACK/NACK data packet
	EXIT   = 6    # exit task
	SLEEP  = 7	  # sleep no records

class BOOMclient:

	class StateMachine:
		_event = []
		def __init__(self):
			self._init = 1
		def pop(self)-> STATE:
			if(len(self._event)==0): return STATE.EMPTY
			return self._event.pop()
		def push(self,state: STATE):
			self._event.append(state)
		def top(self)-> STATE:
			if(len(self._event)==0): return STATE.EMPTY
			return self._event[-1]
		def len(self):
			return len(self._event)
		def clear(self):
			del self._event[:]

	def __init__(self,id,executor = None):
		global config
	#--------------------------------
		self.id = id
		self.executor = executor
	#--------------------------------
		self.state = self.StateMachine()
		self.wsm = SMDR() # writer
		self.rsm = SMDR() # reader
		self.dup = SMDR() # Sometime dup records
		self.sql = SMDR_SQL() #sql
		self.data_from_socket = bytes()
		self.data_to_socket = bytes()
	#--------------------------------
		self._timeout_read = float(config.get(self.id,'timeout_read')) #sec
		self._delay_write = float(config.get(self.id,'delay_write')) #sec
		self._delay_req = float(config.get(self.id,'polling_time')) #sec
		self.rsm.setparity(SMDR_PARITY.ODD)
		self.wsm.setparity(SMDR_PARITY.ODD)
	#--------------------------------
	async def run(self, loop, reader, writer, ServiceCtl = None):
		self.state.clear()
		err = SMDR_ERR.OK
		ack = 0
		while True:
			
			if( ServiceCtl!=None and ServiceCtl.needStop() ):
				break;

			try: 
				debug("{2} -> State: {0} len:{1}".format(self.state.top(),self.state.len(),self.id))
#				soft sleep
				if( self.state.top() == STATE.SLEEP ): 
					self.state.pop()
#					Fast stop service if delay_req is too big
					for tick in range(int(self._delay_req)):
						await asyncio.sleep(1)
						if( ServiceCtl!=None and ServiceCtl.needStop() ):
							self.state.push(STATE.EXIT)
							break;
					continue
				# REQUEST DATA
				if( self.state.top() == STATE.REQ ): 
					self.state.pop()
					if( self.wsm.write(SMDR_CMD.REQ) == SMDR_ERR.OK):
						self.data_to_socket = bytes(self.wsm)
					else:
						self.data_to_socket = bytes(0)
					self.state.push(STATE.READ)
					self.state.push(STATE.WRITE)
					continue
				# READ FROM SOCKET
				if( self.state.top() == STATE.READ ):
					self.state.pop()
					try:
						self.data_from_socket = await asyncio.wait_for(reader.read(1024),timeout=self._timeout_read)
						if( reader.at_eof()): 
							self.state.push(STATE.EXIT)  # EOF
						else:
							self.state.push(STATE.PARSE)
					except asyncio.TimeoutError:
						self.state.push(STATE.REQ) # timeout it happened, try REQ again
						continue
					except:
						self.state.push(STATE.EXIT)  # EOF
						continue
					continue
				# WRITE TO SOCKET
				if( self.state.top() == STATE.WRITE ):  
					self.state.pop()
					try:
						writer.write(self.data_to_socket)
						await writer.drain()
						await asyncio.sleep(self._delay_write) # strange work asyncio/sometime data not be flushed
					except:
						self.state.push(STATE.EXIT)  # EOF
					continue
				# PARSE ERROR 
				if( self.state.top() == STATE.ERROR ):  
					self.state.pop()
					if( err == SMDR_ERR.PARITY ):
						np = int(self.rsm.getparity().value)^int(SMDR_PARITY.EVEN.value)^int(SMDR_PARITY.ODD.value)
						self.rsm.setparity(SMDR_PARITY(np))
						self.wsm.setparity(SMDR_PARITY(np))
						debug("{0} -> Parity error: auto correction".format(self.id))
					else:
						self.state.push(STATE.EXIT)  # 
					continue
				# ACK RECEIVED DATA ( if ACK ->PBX delete record in SDRAM, if NACK -> PBX repeat record )
				if( self.state.top() == STATE.ACK ):
					self.state.pop()
					a = SMDR_RET.ACK
					if(ack): a = SMDR_RET.NACK
					if(self.wsm.write(SMDR_CMD.CRESPONSE,ret=a,seq=self.rsm['seq']) == SMDR_ERR.OK): 
						self.data_to_socket = bytes(self.wsm)
					else:
						self.data_to_socket = bytes()
					self.state.push(STATE.WRITE)
					ack = 0
					continue
				# EMPTY ( Default state )
				if( self.state.top() == STATE.EMPTY ):  # EMPTY STACK -> PUSH REQUEST TO SERVER
					self.state.push(STATE.REQ)
					continue
				if( self.state.top() == STATE.EXIT ):  # EXIT WHILE
					break
				# PARSE RECEIVED DATA
				if( self.state.top() == STATE.PARSE ):
					self.state.pop()
					err = self.rsm.read(self.data_from_socket)
					if(err != SMDR_ERR.OK):
						self.state.push(STATE.ERROR)
						continue
					if(len(self.rsm)<len(self.data_from_socket)): # continue parse buffer have more 1 record
						self.data_from_socket = self.data_from_socket[len(self.rsm):]
						self.state.push(STATE.PARSE)
					cmd = self.rsm['cmd']
					if(cmd == SMDR_CMD.SRESPONSE):	# 'parity' -> state_error , 'norecord' -> set the timer
						debug("{1} -> server response: {0}".format(self.rsm['response'],self.id))
						if(self.rsm['response'] == SMDR_RESPONSE.PARITY ):
							err = SMDR_ERR.PARITY
							self.state.push(STATE.ERROR)
						if(self.rsm['response']	== SMDR_RESPONSE.NORECORD ):
							self.state.push(STATE.SLEEP)
					if(cmd == SMDR_CMD.STATUS):
						debug("{1} -> server status: {0}".format(self.rsm['ret'],self.id))
						nothing_todo = True
					if(cmd == SMDR_CMD.DATA):
						if ( self.executor != None):
							ack = await loop.run_in_executor(self.executor,self.output_data_to_stream) # sync_to_async mode
						else:
							ack = self.output_data_to_stream() # sync mode
						self.state.push(STATE.ACK)
					continue
			except:
				break
		debug("{0} -> Terminate connection".format(self.id))
		return 0

	def output_data_to_stream(self):
		global config
		
		def _str(data: list,sep="")-> str:
			return sep.join(chr(i) for i in data)
# DUP RECORD may be happened
		if( self.dup.record.raw == self.rsm.record.raw ):
			debug("{0}->{1}".format(self.id,"DUP!!!!!!!!!!!!!!!!!!"))
			return 0

		debug("{0}->{1}".format(self.id,_str(self.rsm.record.raw[1:-1])))
		
		# -------------- RAW FILE
		self.output_raw()
		# -------------- CSV FILE
		self.output_csv()
		# -------------- SQL FILE
		self.output_sql()
		
		self.dup.record.raw = self.rsm.record.raw
		
		return 0


	def output_raw(self):
		def _str(data: list,sep="")-> str:
			return sep.join(chr(i) for i in data)
		if( config.get(self.id,'filename') != 'none'):
			path = config.get(self.id,'path')
			try:
				if( os.access(path,os.W_OK) == False ):
					os.makedirs(path,exist_ok=True)
			except:
				debug('{0}-> make dir {1} failed.'.format(self.id,path))
			
			d = datetime.datetime.now()
			filename = path+'\\'+config.get(self.id,'filename').format(year=d.year,month=d.month,day=d.day,id=self.id)
		
			debug('{0}->{1}'.format(self.id,filename))
			try:
				fd = open(filename,'a+')
				fd.write(_str(self.rsm.record.raw[:])+'\n')
				fd.close()
			except OSError:
				debug('{0}-> write to {1} failed.'.format(self.id,filename))
				fd.close()

	def output_csv(self):
		if( config.get('csv','filename') != 'none'):
			path = config.get('main','path')
			try:
				if( os.access(path,os.W_OK) == False ):
					os.makedirs(path,exist_ok=True)
			except:
				debug('{0}-> make dir {1} failed.'.format(self.id,path))
			
			d = datetime.datetime.now()
			filename = path+'\\'+config.get('csv','filename').format(year=d.year,month=d.month,day=d.day,id=self.id)
		
			debug('{0}->{1}'.format(self.id,filename))
			
			if os.access(filename, os.F_OK):
				bHeader = False
			else:
				bHeader = True
				header = 'id;'
				for key in self.rsm.record:
					header += '{0};'.format(key)
			record = '{0};'.format(self.id)
			for key in self.rsm.record:
				record += '{0};'.format(self.rsm.record[key])
				
			try:
				fd = open(filename,'a+')
				if( bHeader ): fd.write(header+'\n')
				fd.write(record+'\n')
				fd.close()
			except OSError:
				debug('{0}-> write to {1} failed.'.format(self.id,filename))
				fd.close()

	def output_sql(self):
		if( config.get('sql','host') == 'none'):
			return None
		host = config.get('sql','host')
		port = config.get('sql','port') 
		user = config.get('sql','username')
		pwd =  config.get('sql','password')
		db =   config.get('sql','database')
		table = config.get('sql','table')
		# Lost record try reconnect next time
		if ( self.sql.cnx == None and self.sql.open(db,user,pwd,host) == None ):
			return None
		for i in range(2):
			if(self.sql.write(self.id,self.rsm.record)):
				break
		debug('Write to sql')
		