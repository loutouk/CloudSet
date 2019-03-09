# Author: Louis Boursier
# This class handles the data and database part of the application

import sqlite3

class Database:
	# by default, the database is regenerated
	def __init__(self, dbFileLocation, init):
		self.dbFileLocation = dbFileLocation
		self.conn = sqlite3.connect(self.dbFileLocation)
		if init == True:
			self.create_database()
		self.conn.commit()
		

	# when the database object is destroyed, we also want to close the connection with the datatabse
	def __del__(self):
		self.conn.close()

	def create_user(self, email, password, initialSet, initialFile):
		# we create automatically and transparently the first set for the user
		# we want to have both operations successful, or we cancel everything, hence the transaction
		res = self.conn.cursor().execute('INSERT INTO user (email, password) VALUES(?, ?)', (email, password,))
		res = self.conn.cursor().execute('INSERT INTO cloudset (name, userId) VALUES(?, (SELECT id from user where email = ?))', (initialSet,email,))
		# create a file and link it to the default set so that the default set is the parent of
		# TODO hide the file linked to the default set so that the default set always remain the super parent
		self.conn.commit()
		self.create_file(initialFile, "dummyId", email)
		self.associate_set_to_file(initialSet, initialFile, email)
		return res

	def get_user_password(self, email):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT password FROM user where email = ?', (email,)).fetchall()
		return res

	def user_exists(self, email):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT email FROM user where email = ?', (email,)).fetchall()
		return res

	def file_exists(self, fileName, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT file.name FROM file INNER JOIN user ON user.id = file.userId where user.email = ? AND file.name = ?', (userEmail,fileName,)).fetchall()
		return res

	def set_exists(self, setName, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT cloudset.name FROM cloudset INNER JOIN user ON user.id = cloudset.userId where user.email = ? AND cloudset.name = ?', (userEmail,setName,)).fetchall()
		return res

	def create_file(self, fileName, driveId, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('INSERT INTO file (name, driveId, userId)  VALUES(?, ?, (select id from user where email = ?))', (fileName,driveId,userEmail,)).fetchall()
		self.conn.commit()
		return res

	def create_set(self, setName, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('INSERT INTO cloudset (name, userId)  VALUES(?, (select id from user where email = ?))', (setName,userEmail,)).fetchall()
		self.conn.commit()
		return res

	def associate_set_to_file(self, setName, fileName, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('''INSERT INTO cloudsetMapFile (fileId, cloudsetId)  
			VALUES((select file.id from file INNER JOIN user ON user.id = file.userId where user.email = :email and file.name = :fileName), 
			(select cloudset.id from cloudset INNER JOIN user ON user.id = cloudset.userId where user.email = :email and cloudset.name = :setName))''', 
			{"email":userEmail, "setName":setName, "fileName":fileName}).fetchall()
		self.conn.commit()
		return res

	def disassociate_set_to_file(self, setName, fileName, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('''DELETE FROM cloudsetMapFile WHERE 
			cloudsetMapFile.fileId IN 
			(select file.id from file INNER JOIN user ON user.id = file.userId where user.email = :email and file.name = :fileName) AND 
			cloudsetMapFile.cloudsetId IN 
			(select cloudset.id from cloudset INNER JOIN user ON user.id = cloudset.userId where user.email = :email and cloudset.name = :setName)''', 
			{"email":userEmail, "setName":setName, "fileName":fileName})
		self.conn.commit()
		return res

	def deleteFile(self, fileName, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		self.conn.cursor().execute("PRAGMA foreign_keys = ON")
		res = self.conn.cursor().execute('''DELETE FROM file WHERE 
			file.id IN 
			(select file.id from file INNER JOIN user ON user.id = file.userId where user.email = :email and file.name = :fileName)''', 
			{"email":userEmail, "fileName":fileName})
		self.conn.commit()
		return res

	def get_user_files(self, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT file.name, file.id FROM file LEFT JOIN user ON user.id = file.userId where user.email = ?', (userEmail,)).fetchall()
		return res

	def get_user_file_drive_id(self, userEmail, fileName):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT file.driveId FROM file LEFT JOIN user ON user.id = file.userId where user.email = ? and file.name = ?', (userEmail,fileName,)).fetchall()
		return res

	def get_user_sets(self, userEmail):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('SELECT cloudset.name, cloudset.id FROM cloudset LEFT JOIN user ON user.id = cloudset.userId where user.email = ?', (userEmail,)).fetchall()
		return res

	def get_user_files_by_sets(self, userEmail, sets):
		self.conn = sqlite3.connect(self.dbFileLocation)
		sets_string = repr(sets).replace('[','').replace(']','').replace('\'','"')
		res = self.conn.cursor().execute('''
			SELECT DISTINCT file.name, file.id FROM file 
			LEFT JOIN user ON user.id = file.userId 
			LEFT JOIN cloudsetMapFile ON cloudsetMapFile.fileId = file.id 
			LEFT JOIN cloudset ON cloudset.id = cloudsetMapFile.cloudsetId 
			where user.email = ? and cloudset.name IN (%s)''' % sets_string 
			, (userEmail,)).fetchall()
		return res

	def get_user_files_by_ids(self, userEmail, filesIds):
		self.conn = sqlite3.connect(self.dbFileLocation)
		filesIds_string = repr(filesIds).replace('[','').replace(']','').replace('\'','"')
		res = self.conn.cursor().execute('''
			SELECT DISTINCT file.name, file.id FROM file 
			LEFT JOIN user ON user.id = file.userId 
			where user.email = ? and file.id IN (%s)''' % filesIds_string 
			, (userEmail,)).fetchall()
		return res

	def get_files_per_cloudset(self, email):
		self.conn = sqlite3.connect(self.dbFileLocation)
		res = self.conn.cursor().execute('''
			SELECT DISTINCT cloudsetMapFile.cloudsetId, cloudsetMapFile.fileId FROM cloudsetMapFile 
			LEFT JOIN file on file.id = cloudsetMapFile.fileId 
			LEFT JOIN user on user.id = file.userId WHERE email = ?
			ORDER BY cloudsetMapFile.cloudsetId'''
			, (email,)).fetchall()
		return res

	def create_database(self):
		query = """CREATE TABLE IF NOT EXISTS user(
					  id INTEGER PRIMARY KEY,
					  email TEXT NOT NULL UNIQUE ON CONFLICT IGNORE,
					  password TEXT NOT NULL
					)"""
		res = self.conn.cursor().execute(query)

		query = """CREATE TABLE IF NOT EXISTS cloudset(
		  id INTEGER PRIMARY KEY,
		  userId INTEGER,
		  name TEXT NOT NULL,
		  UNIQUE(userId, name) ON CONFLICT IGNORE,
		  FOREIGN KEY(userId) REFERENCES user(id) 
			  ON UPDATE CASCADE 
			  ON DELETE CASCADE 
		)"""
		res = self.conn.cursor().execute(query)

		query = """CREATE TABLE IF NOT EXISTS file(
		  id INTEGER PRIMARY KEY,
		  userId INTEGER,
		  name TEXT NOT NULL,
		  driveId TEXT NOT NULL,
		  UNIQUE(userId, name) ON CONFLICT IGNORE,
		  CONSTRAINT fk_userId FOREIGN KEY(userId) REFERENCES user(id) ON DELETE CASCADE 
		)"""
		res = self.conn.cursor().execute(query)
		
		query = """CREATE TABLE IF NOT EXISTS cloudsetMapFile(
		  id INTEGER PRIMARY KEY,
		  cloudsetId INTEGER,
		  fileId INTEGER,
		  CONSTRAINT fk_cloudsetId FOREIGN KEY(cloudsetId) REFERENCES cloudset(id) ON DELETE CASCADE,
		  CONSTRAINT fk_fileId FOREIGN KEY(fileId) REFERENCES file(id) ON DELETE CASCADE 
		)"""
		res = self.conn.cursor().execute(query)
		self.conn.commit()