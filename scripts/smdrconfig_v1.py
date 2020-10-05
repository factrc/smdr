import sys
import os
import configparser
import datetime


class Configuration:

	def __init__(self,filename = 'smdr.ini'):
		self.init = False
		self.filename = filename
		try:
			self.config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
			self.config.add_section('main')
			self.config.add_section('sql')
			self.config.add_section('csv')
			#------------------
			self.config.set('main','delay_write','0.3')
			self.config.set('main','timeout_read','10')
			self.config.set('main','polling_time','60')
			self.config.set('main','max_task','15')
			self.config.set('main','filename','none')
			self.config.set('main','path','c:\\smdr\\')
			self.config.set('main','host','127.0.0.1')
			self.config.set('main','port','60010')
			self.config.set('main','debug','False')
			self.config.set('main','service','False')
			#------------------
			self.config.set('sql','host','none')
			self.config.set('sql','port','3306')
			self.config.set('sql','username','root')
			self.config.set('sql','password','root')
			self.config.set('sql','database','pbx')
			self.config.set('sql','table','records')
			self.config.set('sql','format','asis')
			#------------------
			self.config.set('csv','filename','none')
			self.config.set('csv','path','c:\\smdr\\')
			
			self.config.read(self.filename)
			self.init = True
			self.parse()
		except:
			self.init = False
			
	def __len__(self):
		return len(self.config.sections())-3
	def ids(self):
		for i in self.config.sections():
			if( i not in ['main','sql','csv'] ):
				yield i
	def get(self, id: str, name: str):
		if( self.config.has_option(id,name) == False and id not in ['main','sql','csv'] ): id = 'main'
		return self.config.get(id,name)
