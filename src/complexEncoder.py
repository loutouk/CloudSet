import json

class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        return obj.reprJSON()