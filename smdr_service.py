import sys
sys.path.append('scripts')
import win32serviceutil
import win32service
import win32event
import servicemanager
import winreg
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
from boom import BOOMclient
from boom import debug


config = Configuration(SMDR_CONFIG_NAME)
clients = {}

class SMDRService (win32serviceutil.ServiceFramework):
	_svc_name_ = "SMDR Service for PBX"
	_svc_display_name_ = "SMDR Service"
	_svc_description_ = "SMDR Service for PBX"
	
	def __init__(self,args):
		win32serviceutil.ServiceFramework.__init__(self,args)
		self.hWaitStop = win32event.CreateEvent(None,0,0,None)
		self.timeout = 0
		self.bStop = False

	def SvcStop(self):
		self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
		win32event.SetEvent(self.hWaitStop)
		self.bStop = True
		
	def SvcDoRun(self):
		winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\smdrService')
		self.main()  

	def needStop(self):
		if( self.bStop == True or win32event.WaitForSingleObject(self.hWaitStop, self.timeout) == win32event.WAIT_OBJECT_0 ):
			self.bStop = True
		return self.bStop
	
	
	async def mytask(self,client: BOOMclient, loop):
		global config
	
		addr = config.get(client.id,'host')
		port = config.get(client.id,'port')
	
		while self.bStop == False:
			rc = win32event.WaitForSingleObject(self.hWaitStop, self.timeout)
			if rc == win32event.WAIT_OBJECT_0:
				self.bStop = True
				break
			try:
				reader, writer = await asyncio.open_connection(addr,port,loop=loop)
				debug("Connection to:",writer.get_extra_info('peername')) # debug
			except:
				debug("{0} -> Connect failed :(".format(client.id))
				await asyncio.sleep(5) #reconnect delay
				pass
				continue
			clientInfo = writer.get_extra_info('peername')
			clientInfo = "{0}:{1}({2})".format(clientInfo[0],clientInfo[1],client.id)
			aa = datetime.datetime.now()
			aaa = '{0}/{1}/{2}-{3}:{4}:{5}'.format(aa.year,aa.month,aa.day,aa.hour,aa.minute,aa.second)
			debug('service'," Task {0} {1}-> Start read/write".format(client.id,aaa))
			debug("{0} -> Start read/write with server:".format(clientInfo))
			ret = await client.run(loop,reader,writer,self)
			aa = datetime.datetime.now()
			aaa = '{0}/{1}/{2}-{3}:{4}:{5}'.format(aa.year,aa.month,aa.day,aa.hour,aa.minute,aa.second)
			debug('service'," Task {0} {1}-> Stop read/write".format(client.id,aaa))
			debug("{0} -> Close the client socket".format(client.id))
			try:
				writer.close()
			except:
				debug('service'," Task {0} -> Exception it happened: close socket".format(client.id))
			debug("{0} -> Waiting n... seconds :)".format(client.id))
			await asyncio.sleep(5) #reconnect delay
			
   
	def main(self):
		global clients,config
		loop = asyncio.get_event_loop()
		#====
		def task_done(task):
			global clients
			del clients[task]
			if len(clients) == 0:
				loop = asyncio.get_event_loop()
				loop.stop()
		#====
		workers = int(config.get('main','max_task'))
		executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
		for id in config.ids():
			smdr = BOOMclient(id,executor)
			task = asyncio.Task(self.mytask(smdr,loop))
			clients[task] = smdr
			debug("Create task id({0})".format(id))
			task.add_done_callback(task_done)
		if(len(config)>0):  # if no task exit
			loop.run_forever()
			
		loop.close()

		
if __name__ == '__main__':
	if len(sys.argv) == 1:
		servicemanager.Initialize()
		servicemanager.PrepareToHostSingle(SMDRService)
		servicemanager.StartServiceCtrlDispatcher()
	else:
		win32serviceutil.HandleCommandLine(SMDRService)
