from keras.applications.densenet import DenseNet201
from keras.models import Model
from PIL import Image
from keras import optimizers
from keras.layers import Input, Flatten, Dense, GlobalAveragePooling2D
from keras.layers.convolutional import Conv2D
from keras.callbacks import EarlyStopping
from keras.callbacks import ModelCheckpoint
from keras.callbacks import TensorBoard
from keras.callbacks import CSVLogger
from keras.callbacks import ReduceLROnPlateau
from keras.models import load_model
import keras.backend as K
from keras.preprocessing.image import ImageDataGenerator
import tensorflow as tf
import numpy as np
import pandas as pd
import os, cv2
from keras.utils import to_categorical
from tqdm import tqdm
from config import conf

conf = conf()

base_model = DenseNet201(include_top=False, weights='imagenet')
# base_model.summary()

img_input = Input(shape=(conf.input_shape), name = 'image_input')
output_densenet_conv = base_model(img_input)

# changes...
x = Conv2D(256, 5, activation='elu')(output_densenet_conv)
x = Conv2D(32, 3, activation='elu')(x)
x = Flatten(name='flatten')(x)
x = Dense(256, activation='elu')(x)
out = Dense(conf.nclasses, activation='softmax')(x)

predicted_output = out
model = Model(input=img_input, output=predicted_output)

for layer in base_model.layers:
   layer.trainable = False

if conf.resume_training:
	del model
	model = load_model(conf.save_model_path+ "best_model.hdf5")

model.summary()
early_stopping = EarlyStopping(monitor='val_loss', min_delta=0, patience=5, verbose=0, mode='auto')
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
checkpointer = ModelCheckpoint(filepath=conf.save_model_path+ "best_model.hdf5", 
					verbose=1, monitor='val_acc', save_best_only=True, 
					save_weights_only=False, mode='max', period=1)

tf_board = TensorBoard(log_dir=os.path.join(conf.log_path, "summary"), 
				histogram_freq=100, 
				write_graph=True, write_images=False)
reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.2, patience=10, min_lr=1e-6)
csv_logger = CSVLogger(os.path.join(conf.log_path, "train_log.csv"))

##data loading
def load_process_data(image_path, label_path, model='DR'):
	label_data = pd.read_csv(label_path).iloc[:,:3]
	if model == 'DR': 
		y_train = to_categorical(np.expand_dims(label_data['Retinopathy grade'].as_matrix(), axis=1))
	elif model == 'DME':
		y_train = to_categorical(np.expand_dims(label_data['Risk of macular edema'].as_matrix(), axis=1))
	else: 
		print "Unknow model {} found".format(model) + "Allowed model: DR and DME"
		raise 1
	image_ids = label_data['Image name'].as_matrix()
	x_train = []
	for image_id in tqdm(image_ids):
		path = os.path.join(image_path, image_id + '.jpg')
		orig_eye_data = np.array(Image.open(path).convert('RGB'))
		gray_eye = cv2.cvtColor(orig_eye_data, cv2.COLOR_RGB2GRAY)

		gray_eye[gray_eye > 20.0] = 255.0

		y, x = np.where(gray_eye == 255.0)

		# remove background
		eye_data = orig_eye_data[np.min(y):np.max(y), np.min(x):np.max(x)]
		# print eye_data.shape, conf.resize_to, conf.resampler_choice
		resized_image = cv2.resize(eye_data, conf.resize_to, interpolation = conf.resampler_choice)
		x_train.append(resized_image)
	return (np.array(x_train)[:int(0.7*len(x_train))], y_train[:int(0.7*len(x_train))]),\
		 (np.array(x_train)[int(0.7*len(x_train)):], y_train[int(0.7*len(x_train)):])


(x_train, y_train), (x_valid, y_valid) = load_process_data(conf.image_data_path, conf.label_path, conf.model)

# model fitting
if not conf.data_augmentation:
	print('Not using data augmentation.')
	model.fit(x_train, y_train,
			  batch_size=conf.batch_size,
			  epochs=conf.epochs,
			  validation_split=conf.validation_split,
			  callbacks=[early_stopping, checkpointer, tf_board, csv_logger],
			  shuffle=True)
else:
	print('Using real-time data augmentation.')
	datagen = ImageDataGenerator(
			featurewise_center=False,  # set input mean to 0 over the dataset
			samplewise_center=False,  # set each sample mean to 0
			featurewise_std_normalization=False,  # divide inputs by std of the dataset
			samplewise_std_normalization=False,  # divide each input by its std
			zca_whitening=False,  # apply ZCA whitening
			rotation_range=0,  # randomly rotate images in the range (degrees, 0 to 180)
			width_shift_range=0.1,  # randomly shift images horizontally (fraction of total width)
			height_shift_range=0.1,  # randomly shift images vertically (fraction of total height)
			horizontal_flip=True,  # randomly flip images
			vertical_flip=False)  # randomly flip images

	# Compute quantities required for feature-wise normalization
	# (std, mean, and principal components if ZCA whitening is applied).
	datagen.fit(x_train[:10])

	# Fit the model on the batches generated by datagen.flow().
	model.fit_generator(datagen.flow(x_train, y_train, 
						batch_size=conf.batch_size),
						epochs=conf.epochs,
						validation_data = [x_valid, y_valid],
						# validation_split = conf.validation_split,
						callbacks=[early_stopping, checkpointer, tf_board, csv_logger])