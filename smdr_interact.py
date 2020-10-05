import sys
sys.path.append('scripts')
import os
import asyncio
import random
import time
import concurrent.futures
import datetime
from enum import Enum


from writers_v1 import SMDR_SQL
from smdrconfig_v1 import Configuration
from smdr_v1 import *
from config import SMDR_CONFIG_NAME
from boom import BOOMclient
from boom import debug

config = Configuration(SMDR_CONFIG_NAME)

async def mytask(client: BOOMclient, loop):
	global config
	
	addr = config.get(client.id,'host')
	port = config.get(client.id,'port')
	
	while True:
		try:
			reader, writer = await asyncio.open_connection(addr,port)#,loop=loop)
			debug("Connection to:",writer.get_extra_info('peername')) # debug
		except:
			debug("{0} -> Connect failed :(".format(client.id))
			debug('service',"{0} -> Some connect".format(client.id))			
			await asyncio.sleep(5) #reconnect delay
			pass
			continue
		clientInfo = writer.get_extra_info('peername')
		clientInfo = "{0}:{1}({2})".format(clientInfo[0],clientInfo[1],client.id)
		debug("{0} -> Start read/write with server:".format(clientInfo))
		ret = await client.run(loop,reader,writer)
		debug('service',"{0} -> Some stop".format(clientInfo))
		debug("{0} -> Close the client socket".format(clientInfo))
		writer.close()
		debug("{0} -> Waiting n... seconds :)".format(clientInfo))
		await asyncio.sleep(5) #reconnect delay


clients = {}

def main():
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
		task = asyncio.Task(mytask(smdr,loop))
		clients[task] = smdr
		debug("Create task id({0})".format(id))
		task.add_done_callback(task_done)
	
	if(len(config)>0):
		loop.run_forever()
		
	loop.close()

if __name__ == '__main__':
	main()
