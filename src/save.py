		# finding parent
		for i in range(len(sortedDict)):
			dic = sortedDict[i]
			maxParentSize = 100000000000000
			for j in range(len(sortedDict)):
				otherDics = sortedDict[j]
				if otherDics != dic:
					if dic.viewitems() < otherDics.viewitems() and len(otherDics) <= maxParentSize:
						maxParentSize = len(otherDics)
						cloudsets[sortedDictOrder[j]].children.append(cloudsets[sortedDictOrder[i]])
						

		# find the biggest cloudset, and use it to create the JSON file
		maxSetSize = -1;
		biggestSet = cloudsets[sortedDictOrder[len(sortedDictOrder)-1]]

		print biggestSet
		
		# erase the content and write
		f = open(os.path.join('static','data','data.json'), "w")
		f.write(biggestSet.toJSON())