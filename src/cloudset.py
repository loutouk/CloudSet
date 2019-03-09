import json
from complexEncoder import ComplexEncoder

class Cloudset:
	def __init__(self, name, dbId):
		self.name = name
		self.dbId = dbId
		self.children = []
		self.set = {}

	def reprJSON(self):
		if(len(self.children) > 0):
			return dict(children=self.children, name=self.name)
		else:
			return dict(name=self.name, size=len(self.set))

	def __repr__(self):
		return json.dumps(self.reprJSON(), cls=ComplexEncoder, indent=1)

	def toJSON(self):
		return json.dumps(self.reprJSON(), cls=ComplexEncoder, indent=1)

