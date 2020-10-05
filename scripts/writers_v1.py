import mysql.connector
from imsneax_v1 import IMSRecord
from functools import reduce

class SMDR_SQL:

	def __init__(self):
		self.cnx = None
		
	def open(self,db,username,pwd,ipaddr):
		try:
			self.cnx = mysql.connector.connect(user=username,password=pwd,host=ipaddr,database=db,connection_timeout=2,charset="utf8",auth_plugin='mysql_native_password')
		except mysql.connector.Error as err:
			self.cnx = None
		return self.cnx
		
	def write(self, id, msg: IMSRecord):
		if ( self.cnx != None):
			try:
				header = 'INSERT INTO RECORDS ( `name`,`'+'`,`'.join(msg)+'`) '
				bottom = 'VALUES ({},'.format(id)+str(list(msg.value.values())).strip('[]')+')'
				cursor = self.cnx.cursor()
				cursor.execute(header+bottom)
				cursor.close()
				self.cnx.commit()
				return True
			except mysql.connector.Error as err:
				self.close()
		return False
	def close(self):
		if ( self.cnx !=None):
			self.cnx.close()
			self.cnx = None
	
