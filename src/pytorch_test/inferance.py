
class DRGradeTester():
	#--------------------------------------------------------------------------------  
	#---- Test the trained network 
	#---- pathDirData - path to the directory that contains images
	#---- pathFileTrain - path to the file that contains image paths and label pairs (training set)
	#---- pathFileVal - path to the file that contains image path and label pairs (validation set)
	#---- nnArchitecture - model architecture 'DENSE-NET-121', 'DENSE-NET-169' or 'DENSE-NET-201'
	#---- nnIsTrained - if True, uses pre-trained version of the network (pre-trained on imagenet)
	#---- nnClassCount - number of output classes 
	#---- trBatchSize - batch size
	#---- trMaxEpoch - number of epochs
	#---- transResize - size of the image to scale down to (not used in current implementation)
	#---- transCrop - size of the cropped image 
	#---- launchTimestamp - date/time, used to assign unique name for the checkpoint file
	#---- checkpoint - if not None loads the model and continues training
	
	def test (self, pathTestData, pathsModel1, pathsExpertmodel, nnArchitecture, nnClassCount, nnIsTrained, trBatchSize, transResize, transCrop, launchTimeStamp):   
		
		#-------------------- SETTINGS: DATA TRANSFORMS, TEN CROPS
		normalize = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
		
		#-------------------- SETTINGS: DATASET BUILDERS
		transformList = []
		transformList.append(transforms.Resize(transResize))
		transformList.append(transforms.TenCrop(transCrop))
		transformList.append(transforms.Lambda(lambda crops: torch.stack([transforms.ToTensor()(crop) for crop in crops])))
		transformList.append(transforms.Lambda(lambda crops: torch.stack([normalize(crop) for crop in crops])))
		transformSequence=transforms.Compose(transformList)
		
		datasetTest = DatasetGenerator(pathImageDirectory=pathTestData, transform=transformSequence, nclasses = 4)
		dataLoaderTest = DataLoader(dataset=datasetTest, batch_size=1, num_workers=8, shuffle=False, pin_memory=False)
	   	
	   	outGT = torch.FloatTensor()
		outPRED = torch.FloatTensor()

		model.eval()
		
		for i, (input, target) in enumerate(dataLoaderTest):
			
			for pathModel, pathExpertmodel in zip(pathsModel1, pathsExpertmodel):
			model = torch.load(pathModel)

			# target = target.cuda()
			outGT = torch.cat((outGT, target), 0)
			
			bs, n_crops, c, h, w = input.size()
			
			varInput = torch.autograd.Variable(input.view(-1, c, h, w).cuda(), volatile=True)
			
			out = model(varInput)
			outMean = out.view(bs, n_crops, -1).mean(1)
			
			outPRED = torch.cat((outPRED, outMean.data), 0)

		aurocIndividual = self.computeAUROC(outGT, outPRED, nnClassCount)
		aurocMean = np.array(aurocIndividual).mean()
		
		print ('AUROC mean ', aurocMean)
		
		for i in range (0, len(aurocIndividual)):
			print (CLASS_NAMES[i], ' ', aurocIndividual[i])
		
	 
		return
#-------------------------------------------------------------------------------- 