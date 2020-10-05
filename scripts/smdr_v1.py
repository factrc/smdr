import sys
import functools
from enum import Enum
from imsneax_v1 import IMSRecord

class SMDR_PARITY(Enum):
	NONE = 0
	EVEN = 1
	ODD  = 2

class SMDR_RET(Enum):
	ACK  = 6
	NACK = 15

class SMDR_CMD(Enum):
	INIT 		= 0
	REQ			= 1 
	DATA		= 2
	SRESPONSE	= 3
	CRESPONSE	= 4
	STATUS		= 5
	DISCONNECT	= 6
	
class SMDR_RESPONSE(Enum):
	INIT		= 0
	NORECORD	= 1
	STATUS		= 2
	PARITY		= 3
	ILLEGAL		= 5

class SMDR_ERR(Enum):
	 OK			= 0
	 PARITY		= 1
	 ILLEGAL	= 2
	 COMMAND	= 3
	 
	 
	
#=============================================================
# DataRequest (to PBX)
#	timer response 10sec default value, repeat 6 times. after reset connection
#  sync(1),type(1),len(5),devnum(2),parity(1)
#  sync word - 16
#  type - 1
#
#=============================================================
# Sending data (from PBX)
#	sync(1),type(1),len(5),devnum(2),seq(1),data(n),parity(1)
#	sync word - 16
#	type - 2
#	devnum fixed - "00"
#
#=============================================================
# Server response (from PBX)	
#	sync(1),type(1),len(5),devnum(2),respnum(1),parity(1)
#	sync word - 16
#	type - 3
#	devnum - "00"
#	respnum:
#		1 - no smdr record are buffered
#		2 - status monitoring identifier
#		3 -	parity error
#		5 - error in received text ( illegal )
#
#=============================================================
# Client response (to PBX)	
#	sync(1),type(1),len(5),devnum(2),seqnum(1),ACK/NACK(1),parity(1)
#	sync word - 16
#	type - 4
#	devnum - "00"
#	ACK/NACK:
#		6  - ACK
#		15 - NACK
#
#=============================================================
# Status Monitoring (from/to PBX)	
#	sync(1),type(1),len(5),devnum(2),CDI(1),ACK/NACK(1),parity(1)
#	sync word - 16
#	type - 5
#	devnum - "00"
#	CDI - "0"
#	ACK/NACK:
#		6  - ACK
#		15 - NACK
#
#=============================================================
# Connection Disconnect (to PBX)	
#	sync(1),type(1),len(5),devnum(2),ACK/NACK(1),parity(1)
#	sync word - 16
#	type - 6
#	devnum - "00"
#

class SMDR:
	def __init__(self, bDebug = False ):
		self.bDebug = bDebug	
		self.record = IMSRecord()	
		self.Parity = SMDR_PARITY.NONE
		self.PacketLen = 0
		self.raw = bytes()
		self.fAction = dict( 
							zip([SMDR_CMD.INIT,SMDR_CMD.REQ,SMDR_CMD.DATA,
								 SMDR_CMD.SRESPONSE,SMDR_CMD.CRESPONSE,
								 SMDR_CMD.STATUS,SMDR_CMD.DISCONNECT
								],[
							(self.readInit,self.writeInit,0),
							(self.readDataReq,self.writeDataReq,2),
							(self.readSendData,self.writeSendData,3),
							(self.readServerResp,self.writeServerResp,3),
							(self.readClientResp,self.writeClientResp,4),
							(self.readStatusMon,self.writeStatusMon,4),
							(self.readDisconnect,self.writeDisconnect,3),
							]))
		self.values = {"cmd":SMDR_CMD.INIT, "seq":0, "response":SMDR_RESPONSE.INIT, "ret": SMDR_RET.ACK, "record":[] }
#==================================================================================================		
	def _log(self, *value):
		if ( self.bDebug ):	print( *value)
		
	def _calc_parity(self, data: bytes)->int:
		parity = functools.reduce(lambda v1,v2: v1^v2, data, 0)
		if( self.Parity == SMDR_PARITY.ODD ): parity = parity^0xFF
		return parity
#==================================================================================================
	def setparity(self,parity: SMDR_PARITY=SMDR_PARITY.NONE):
		self.Parity = parity
	def getparity(self):
		return self.Parity
	def __len__(self):
		return len(self.raw)
	def __getitem__(self, name: str):
		return self.values[name]
	def __bytes__(self):
		return self.raw

	def read(self, data: bytes )-> SMDR_ERR:
		try:
			self.values["cmd"] =  SMDR_CMD.INIT
			cmd = SMDR_CMD(data[1]-0x30) 
			if ( cmd not in self.fAction ): return SMDR_ERR.COMMAND
			self.PacketLen = int(data[2:7])+8
			self.raw = bytes(data[:self.PacketLen])
		except:	
			return SMDR_ERR.ILLEGAL
		self.values["cmd"] = cmd
		parity = self._calc_parity(self.raw[1:self.PacketLen-1])
		self._log("Packet len: {0} Command: {1} Parity: {2}/{3}".format(self.PacketLen,cmd,hex(parity),hex(self.raw[self.PacketLen-1])))
		if( self.raw[self.PacketLen-1] != 0 and self.Parity != SMDR_PARITY.NONE ):
			if( parity != self.raw[self.PacketLen-1] ):
				return SMDR_ERR.PARITY
		if(self.fAction[cmd][2]>len(self.raw[7:self.PacketLen-1])):
			return SMDR_ERR.ILLEGAL
			
		return self.fAction[cmd][0](self.raw[7:self.PacketLen-1])

	def write(self, cmd: SMDR_CMD, **args )-> SMDR_ERR:
		if( cmd not in self.fAction ):
			return SMDR_ERR.COMMAND
		return self.fAction[cmd][1](**args)
#--------------------------------------------------------------
	def readInit(self, data: bytes )-> SMDR_ERR:
		return SMDR_ERR.OK
#-------------- to PBX 		
	def readDataReq(self, data: bytes )-> SMDR_ERR:
		return SMDR_ERR.OK
	def readClientResp(self, data: bytes )-> SMDR_ERR:
		self._log("seqNum:",int(data[2:3]))
		self._log("Return:",SMDR_RET(data[3]))
		self.values["ret"] = SMDR_RET(data[3])
		self.values["seq"] = int(data[2:3])
		return SMDR_ERR.OK
	def readDisconnect(self, data: bytes )-> SMDR_ERR:
		self._log("Return:",SMDR_RET(data[2]))
		self.values["ret"] = SMDR_RET(data[2])
		return SMDR_ERR.OK
#--------------- from PBX
	def readServerResp(self, data: bytes )-> SMDR_ERR:
		ret = SMDR_RESPONSE(int(data[2:3]))
		self._log("Response: code:{0}".format(ret))
		self.values["response"] = ret
		return SMDR_ERR.OK
	def readStatusMon(self, data: bytes )-> SMDR_ERR:
		self._log("Return:",SMDR_RET(data[3]))
		self.values["ret"] = SMDR_RET(data[3])
		return SMDR_ERR.OK
	def readSendData(self, data: bytes )-> SMDR_ERR:
		if( data[3]!=2 or data[-1] != 3 ): return SMDR_ERR.ILLEGAL
		self._log("seqNum:",int(data[2:3]))
		self.values["seq"] = int(data[2:3])
		error = self.record.read(data[3:])
		if ( error ): return SMDR_ERR.ILLEGAL
		return SMDR_ERR.OK
#--------------- from PBX
	def writeServerResp(self, **data )-> SMDR_ERR:
		if( 'response' not in data ): return SMDR_ERR.COMMAND
		ret = [0x16,0x33,0x30,0x30,0x30,0x30,0x33,0x30,0x30,0x30,0x00]
		ret[-2] = int(data["response"].value)+0x30
		ret[-1] = self._calc_parity(ret[1:-1])
		self.raw = bytes(ret)
		return SMDR_ERR.OK
	def writeStatusMon(self, **data )-> SMDR_ERR:
		if( 'ret' not in data ): return SMDR_ERR.COMMAND
		ret = [0x16,0x35,0x30,0x30,0x30,0x30,0x34,0x30,0x30,0x30,0x30,0x00]
		ret[-2] = int(data["ret"].value)
		ret[-1] = self._calc_parity(ret[1:-1])
		self.raw = bytes(ret)
		return SMDR_ERR.OK
	def writeSendData(self, **data )-> SMDR_ERR:
		if( ('record' not in data and 'seq' not in data) or data['seq']<0 or data['seq']>9 ): return SMDR_ERR.COMMAND
		size = "%(s)05d00%(q)01d" % { 's':len(data['record'])+3, 'q':data["seq"]  }
		ret = [0x16,0x32]
		ret.extend([ord(i) for i in size])
		ret.extend(data["record"])
		parity = self._calc_parity(ret[1:])
		ret.append(parity)
		self.raw = bytes(ret)
		return SMDR_ERR.OK
#-------------- to PBX
	def writeInit( self, **data )-> SMDR_ERR:
		return SMDR_ERR.OK
	def writeDataReq( self, **data )-> SMDR_ERR:
		ret = [0x16,0x31,0x30,0x30,0x30,0x30,0x32,0x30,0x30,0x00]
		ret[-1] = self._calc_parity(ret[1:-1])
		self.raw = bytes(ret)
		return SMDR_ERR.OK
	def writeClientResp(self, **data )-> SMDR_ERR:
		if( "seq" not in data and "ret" not in data ): return SMDR_ERR.COMMAND
		ret = [0x16,0x34,0x30,0x30,0x30,0x30,0x34,0x30,0x30,0x30,0x30,0x00]
		ret[-3] = data["seq"]+0x30
		ret[-2] = int(data["ret"].value)
		ret[-1] = self._calc_parity(ret[1:-1])
		self.raw = bytes(ret)
		return SMDR_ERR.OK
	def writeDisconnect(self, **data )-> SMDR_ERR:
		if( "ret" not in data ): return SMDR_ERR.COMMAND
		ret = [0x16,0x36,0x30,0x30,0x30,0x30,0x33,0x30,0x30,0x30,0x00]
		ret[-2] = int(data["ret"].value)
		ret[-1] = self._calc_parity(ret[1:-1])
		self.raw = bytes(ret)
		return SMDR_ERR.OK
