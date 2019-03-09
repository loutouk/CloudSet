import os
from flask import Flask, render_template, request, redirect, flash, url_for, session, abort
from flask_session import Session
from flask_bcrypt import Bcrypt
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from werkzeug.utils import secure_filename
from apiclient.http import MediaFileUpload
from customErrors import DriveFolderNil, DriveFileAdd
import unicodedata
from database import Database
from cloudset import Cloudset
import json
import re

UPLOAD_FOLDER = 'uploads'
DRIVE_FOLDER = "SetCloudDatas"
ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])
# If modifying these scopes, delete the file token.json.
API_SCOPES = 'https://www.googleapis.com/auth/drive'
# Every files should at least belong to the default set
DEFAULT_SET = "DefaultSet"
# The default set should always be the parent of all the others cloudset
# so we give it a file that only it can be linked to
# and ensure that the default set will be linked to all others file add in the future
# TODO set security to ensure those rules
DEFAULT_FILE = "DefaultFile"

# Drive API
store = file.Storage('token.json')
creds = store.get()
if not creds or creds.invalid:
	flow = client.flow_from_clientsecrets('credentials.json', API_SCOPES)
	creds = tools.run_flow(flow, store)
drive_service = build('drive', 'v3', http=creds.authorize(Http()))

class Controller:
	def __init__(self, app):
		self.app = app
		self.bcrypt = Bcrypt(self.app)

	def indexPage(self):
		if "user" in session:
			return self.homePage()
		return render_template('index.html', )

	def registerPage(self):
		return render_template('register.html', )

	def getFilesDict(self):
		self.verifyIdentification()

		db = Database("var/sqlite3.db", False)

		filesList = db.get_user_files(session["user"])
		# file{id => name}
		files = {}
		for currentFile in filesList:
			files[currentFile[1]] = currentFile[0]
		return files

	def getFilesDictPerName(self):
		self.verifyIdentification()

		db = Database("var/sqlite3.db", False)
		filesList = db.get_user_files(session["user"])
		# file{name => id}
		files = {}
		for currentFile in filesList:
			files[currentFile[0]] = currentFile[1]
		return files

	def getSetsDict(self):
		self.verifyIdentification()

		db = Database("var/sqlite3.db", False)
		setsList = db.get_user_sets(session["user"])
		# set{name => id}
		sets = {}
		for currentSet in setsList:
			sets[currentSet[0]] = currentSet[1]
		return sets

	def getCloudsets(self, sets):
		self.verifyIdentification()

		db = Database("var/sqlite3.db", False)

		# cloudsets{id => Cloudset()}
		cloudsets = {}

		for value, key in sets.items():
			cloudsets[key] = Cloudset(value, key)

		linksList = db.get_files_per_cloudset(session["user"])

		# dict {cloudset id , {file id, is linked ?}}
		cloudsetLinks = {}

		parentSet = {}
		for link in linksList:
			cloudsetLinks[link[0]] = {}
			parentSet[link[0]] = {}

		# we browse the links fetched from the db to set the links where they are
		for link in linksList:
			cloudsetLinks[link[0]][link[1]] = True
			cloudsets[link[0]].set = cloudsetLinks[link[0]]

		# now, we want we to place the cloudset into their parent set if they have some

		# first sort from the shortest to the biggest considering the size of their dictionary
		sortedDictOrder = []
		for dict in sorted(cloudsetLinks, key=lambda k: len(cloudsetLinks[k]), reverse=False):
			sortedDictOrder.append(dict)


		sortedDict = []
		for i in sortedDictOrder:
			sortedDict.append(cloudsetLinks[i])

		# finding parent
		for i in range(len(sortedDict)):
			dic = sortedDict[i]
			for j in range(len(sortedDict)):
				otherDics = sortedDict[j]
				if otherDics != dic:
					if len(dic.keys()) < len(otherDics.keys()):
						cloudsets[sortedDictOrder[j]].children.append(cloudsets[sortedDictOrder[i]])

		return cloudsets

	def homePage(self):
		self.verifyIdentification()
		db = Database("var/sqlite3.db", False)
		# set{name => id}
		sets = self.getSetsDict()
		# cloudsets{id => Cloudset()}
		cloudsets = self.getCloudsets(sets)
		# find the biggest cloudset, and use it to create the JSON file
		biggestSet = cloudsets[sets[DEFAULT_SET]]
		data = biggestSet.toJSON()
		return render_template('home.html', data=data)

	def search_files_by_sets(self):
		self.verifyIdentification()

		if request.method == 'POST':
			db = Database("var/sqlite3.db", False)
			# no htmlentities() or equivalent because flask uses its own xss protection while using render_template()
			inputSetsList = request.form.get('cloudsets').encode('UTF-8')
			inputSetsList = inputSetsList.decode('UTF-8')
			authorizedString = bool(re.match('^(?!.*([,\|\&\^\-])\\1{1,})[a-zA-Z0-9 ,\&\-\^\|]+$', inputSetsList))
			if authorizedString == False:
				return render_template("home.html")

			# List all files
			fileList = []
			files = []

			# the coma corresponds to the union operator ( | in Python)
			orderedSetName = []
			orderedSetOperation = []
			leftTermBeginIndex = 0;

			for i in range(len(inputSetsList)):
				if inputSetsList[i] in [",", "&", "^", "-", "|"]:
						orderedSetName.append(inputSetsList[leftTermBeginIndex:i].strip())
						orderedSetOperation.append(inputSetsList[i])
						leftTermBeginIndex = i + 1
			# add the last set name
			orderedSetName.append(inputSetsList[leftTermBeginIndex:len(inputSetsList)].strip())
			# set{name => id}
			sets = self.getSetsDict()
			# cloudsets{id => Cloudset()}
			cloudsets = self.getCloudsets(sets)
			# fi
			filesNames = self.getFilesDict()
			# create an empty set for the Cloudset name which does not exist
			if orderedSetName[0] in sets:
				leftSet = set(cloudsets[sets[orderedSetName[0]]].set.keys())
			else:
				leftSet = set()

			for i in range(1, len(orderedSetName)):
				if orderedSetName[i] in sets:
					rightSet = set(cloudsets[sets[orderedSetName[i]]].set.keys())
				# create an empty set for the Cloudset name which does not exist
				else:
					rightSet = set()
				setOperator = orderedSetOperation[i-1]
				if(setOperator == "," or setOperator == "|"):
					leftSet = leftSet.union(rightSet)
				elif(setOperator == "^"):
					leftSet = leftSet.symmetric_difference(rightSet)
				elif(setOperator == "&"):
					leftSet = leftSet.intersection(rightSet)
				elif(setOperator == "-"):
					leftSet = leftSet.difference(rightSet)



			files = db.get_user_files_by_ids(session["user"], list(leftSet))

			# links file id to their cloudset name
			# fileName => setsName()
			fileMapSets = {}
			for fileId in leftSet:
				# use set to store set name for having no duplicate
				fileMapSets[filesNames[fileId]] = set()
				for c in cloudsets:
					if fileId in cloudsets[c].set:
						fileMapSets[filesNames[fileId]].add(cloudsets[c].name)
			
			# Ask Google Drive API's all files, and return them which have the same name than those in our list
			results = drive_service.files().list(pageSize=10, fields="nextPageToken, files(name, webViewLink)").execute()
			items = results.get('files', [])
			if not items:
				fileList.append('No files found.')
			else:
				for item in items:
						if any(item['name'] in s for s in files):
							fileList.append([item['name'],item['webViewLink']])

			sortedSet = []
			for value, key in sorted(sets.items()):
				sortedSet.append(value)

			return render_template('files.html', files=fileList, fileMapSets=fileMapSets, sets=sortedSet, defaultSet=DEFAULT_SET)

	def init_drive_folder(self):
		file_metadata = {
		    'name': DRIVE_FOLDER,
		    'mimeType': 'application/vnd.google-apps.folder'
		}
		file = drive_service.files().create(body=file_metadata, fields='id').execute()

	def get_drive_folder_id(self, folder_name):
		# look for the google drive folder where we store our data
		results = drive_service.files().list(fields="files(id, name)").execute()
		allDriveFiles = results.get('files', [])
		if not allDriveFiles:
			raise DriveFolderNil("Error: no root file for the name " + folder_name)
		else:
			for file in allDriveFiles:
				if file['name'] == folder_name:
					return file['id']
			raise DriveFolderNil("Error: no root file for the name " + folder_name)

	def upload_file(self):
		self.verifyIdentification()

		if request.method == 'POST':

			db = Database("var/sqlite3.db", False)

			# check if the post request has the file part
			if 'fileToUpload' not in request.files:
				flash('No file part')
				return redirect(request.url)

			file = request.files['fileToUpload']
			# if user does not select file, browser also
			# submit an empty part without filename 
			if file.filename == '':
				flash('No selected file')
				return redirect(request.url)

			root_folder = self.get_drive_folder_id(DRIVE_FOLDER)
			tags = []
			# every files should have the default set to perform operation on them
			tags.append(DEFAULT_SET)

			retrievedTags = request.form.get('tags')
			if(retrievedTags is not None):
				tagsList = retrievedTags.split(",")
				if(len(tagsList)>0):
					for tag in tagsList:
						tags.append(tag.strip())


			if file and self.allowed_file(file.filename):

				# delete the upload temp file folder files on server side each time we upload a new file
				# we only need them temporararily to send them to the google druve server
				# after that we can delete them
				# not mandaotory but avoid to take too much disk space
				# but this will create errors when simultaneous access: solution: one folder per user?
				for the_file in os.listdir(UPLOAD_FOLDER):
				    file_path = os.path.join(UPLOAD_FOLDER, the_file)
				    try:
				        if os.path.isfile(file_path):
				            os.unlink(file_path)
				    except Exception as e:
				        print(e)

				filename = secure_filename(file.filename)

				# if filename already exists for this user in the datatabase, we cancel and inform the user
				fileExists = db.file_exists(filename, session["user"])
				if len(fileExists) > 0:
					flash('Error. File with this name already exists.')
					return redirect(url_for("homePage")) 

				file.save(os.path.join(UPLOAD_FOLDER, filename))
				file_metadata = {'name': filename, 'parents': [root_folder]}
				media = MediaFileUpload(os.path.join(UPLOAD_FOLDER, filename))
				driveFile = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
				driveId = driveFile["id"]
				if(file is None):
					raise DriveFileAdd("Error: could not add the file " + filename + " to the drive")
					flash('Error. File not uploaded.')
				else:
					# file was added to the drive folder, so we should update the database
					# create the file
					db.create_file(filename, driveId, session["user"])
					# if the set already exists, the query will be ignored
					for tag in tags:
						db.create_set(tag, session["user"])
					# link the file to the tags
					for tag in tags:
						db.associate_set_to_file(tag, filename, session["user"])
					flash('File uploaded.')
		
		return redirect(url_for("homePage")) 

	def allowed_file(self, filename):
		return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

	def login(self):
		if request.method == 'POST':
			db = Database("var/sqlite3.db", False)
			# no htmlentities() or equivalent because flask uses its own xss protection while using render_template()
			email = request.form.get('inputEmail')
			inputPassword = request.form.get('inputPassword')
			res = db.get_user_password(email)
			if not res or not self.bcrypt.check_password_hash(res[0][0], inputPassword):
				flash('Wrong credentials.')
			else:
				session["user"] = email
		return self.indexPage()

	def create_login(self):
		if request.method == 'POST':
			db = Database("var/sqlite3.db", False)
			# no htmlentities() or equivalent because flask uses its own xss protection while using render_template()
			email = request.form.get('inputEmail')
			password = request.form.get('inputPassword')	

			emailAlreadyTaken = db.user_exists(email)
			if emailAlreadyTaken:
				flash('Email already taken.')
				return self.indexPage()

			hashedPassword = self.bcrypt.generate_password_hash(password)
			res = db.create_user(email, hashedPassword, DEFAULT_SET, DEFAULT_FILE)
			if res:
				# we create the local folder which is used as temporary storage before sending the file to the cloud
				if not os.path.exists(UPLOAD_FOLDER):
					os.mkdir(UPLOAD_FOLDER)
				# we create its drive folder where we are going to store the datas
				self.init_drive_folder()
				flash('Account created. You can login.')
			else:
				flash('Failed to create account.')
		return self.indexPage()

	def deleteFile(self):
		self.verifyIdentification()

		fileName = request.args.get('fileName').encode('UTF-8').strip()
		fileName = fileName.decode('UTF-8').strip()
		if fileName and fileName != DEFAULT_FILE:
			db = Database("var/sqlite3.db", False)
			driveId = db.get_user_file_drive_id(session["user"], fileName)
			if len(driveId) > 0:
				driveId = driveId[0][0]
				drive_service.files().delete(fileId=driveId).execute()
				res = db.deleteFile(fileName, session["user"])
				return "OK"
		return "NOK"

	def linkFileToCloudset(self):
		self.verifyIdentification()

		fileName = request.args.get('fileName')
		setName = request.args.get('setName')
		toLinked = request.args.get('toLinked')
		if fileName and setName and toLinked and setName != DEFAULT_SET:
			db = Database("var/sqlite3.db", False)
			if(toLinked == "true"):
				res = db.associate_set_to_file(setName, fileName, session["user"])
				return "OK"
			elif(toLinked == "false"):
				res = db.disassociate_set_to_file(setName, fileName, session["user"])
				return "OK"
		return "NOK"

	def logout(self):
		session.clear()
		return self.indexPage()

	def page_not_found(self):
  		return render_template('404.html'), 404

	def verifyIdentification(self):
		if not "user" in session:
			abort(403)
			#return self.logout()
			
