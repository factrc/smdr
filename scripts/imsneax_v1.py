import sys
import functools
import datetime

from enum import Enum


# ---- Former NEAX 2400 IMS Format
#   'A' -	Outgoing trunk calls
#	'E'	-	Incoming trunk calls
# ---- Extended NEAX 2400 IMS Format
#   'H' -	Outgoing trunk calls
#	'I'	-	Incoming trunk calls
# TRUNKROUTE
# TRUNK
# IDENT
# TENANT
# NUMA
# NUMB
# START
# STOP
# ACCOUNT
# CONDITION
# ROUTE1
# ROUTE2
# ANI  
#

class IMSRecord:

	def _str(self, data: bytes,sep='')-> str:
		return sep.join(chr(i) for i in data)

	def __init__(self):
		self.raw = bytes()
		
		self.value = {
			"type":"",
			"trunkroute":"",
			"trunk":"",
			"ident":"",
			"tenant":"",
			"caller":"",
			"called":"",
			"start":"",
			"stop":"",
			'duration':"",
			"condition":"",
			"route1":"",
			"route2":"",
			"ani":""
			}
	
	def read(self, data: bytes )-> int:
		self.raw = data
		return self._parse()
		
	def __len__(self):
		return len(self.raw)
	def __bytes__(self):
		return self.raw
	
	def __getitem__(self,name):
		return self.value[name]
		
	def __iter__(self):
		for i in self.value:
			yield i
	
	def _parse(self):
		s = self._str(self.raw[3:-1])
		type = s[1]
		self.value["trunkroute"] = s[2:5].strip()
		self.value["trunk"]  = s[5:8].strip()
		self.value["ident"]  = s[8:9].strip()
		self.value["tenant"] = s[9:11].strip()
		self.value["start"]  = "{5}-{1}-{0} {2}:{3}:{4}".format(s[19:21],s[17:19],s[21:23],s[23:25],s[25:27],2000+int(s[113:115]))
		self.value["stop"]   = "{5}-{1}-{0} {2}:{3}:{4}".format(s[29:31],s[27:29],s[31:33],s[33:35],s[35:37],2000+int(s[115:117]))
		self.value["condition"] = s[50:53].strip()
		self.value["route1"]   	= s[53:56].strip()
		self.value["route2"]   	= s[56:59].strip()
		self.value["ani"]  	 	= s[95:113].strip()
		if ( type in ['A','H'] ):
				self.value["type"] = 'O'
				self.value["caller"] = s[11:17].strip()
				self.value["called"] = s[59:91].strip()
				if(self.value["called"] == ""): self.value["called"] = self.value["ani"]
		if ( type in ['E','I'] ):
				self.value["type"] = 'I'
				self.value["caller"] = s[59:91].strip()
				self.value["called"] = s[11:17].strip()
				if(self.value["caller"] == ""): self.value["caller"] = self.value["ani"]
		
		at = datetime.datetime.strptime(self.value["start"],'%Y-%m-%d %H:%M:%S')
		bt = datetime.datetime.strptime(self.value["stop"],'%Y-%m-%d %H:%M:%S')
		self.value['duration'] = str(int((bt-at).total_seconds()))
					
		return 0
#	def print_record(self):
#		print("type({0}) ".format(chr(self.type)))
#		s = _str(self.raw[1:-1])
#		print("Record:\n===============\n"
#		"Route: {0}\n"
#		"Trunk: {1}\n"
#		"calling party: {2}\n"
#		"TENANT: {3}\n"
#		"CALLING: {4}\n"
#		"TIME START: {5}\n"
#		"TIME END: {6}\n"
#		"ACCOUNT CODE: {7}\n"
#		"TENANT: {8}\n"
#		"CONDITION: {9}\n"
#		"ROUTE1: {10}\n"
#		"ROUTE2: {11}\n"
#		"CALLED: {12}\n"
#		"METERING: {13}\n"
#		"CALLING OFFICE: {14}\n"
#		"BILLING OFFICE: {15}\n"
#		"CONDITION ADVICE: {17}\n"
#		"AOC: {18}".format(
#		s[2:5],s[5:8],s[8:9],s[9:11],s[11:17],
#		"{5}-{1}-{0} {2}:{3}:{4}".format(s[19:21],s[17:19],s[21:23],s[23:25],s[25:27],2000+int(s[113:115])),
#		"{5}-{1}-{0} {2}:{3}:{4}".format(s[29:31],s[27:29],s[31:33],s[33:35],s[35:37],2000+int(s[115:117])),
#		s[37:47],s[47:50],s[50:53],s[53:56],s[56:59],
#		s[59:91],
#		s[91:95],
#		s[95:99],
#		s[99:103],
#		s[103:113],
#		s[117:118],
#		s[118:124]
#		))
#		print(_str(self.data))
