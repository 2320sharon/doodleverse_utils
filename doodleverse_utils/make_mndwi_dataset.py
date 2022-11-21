# Written by Dr Daniel Buscombe, Marda Science LLC
# for the USGS Coastal Change Hazards Program
#
# MIT License
#
# Copyright (c) 2022, Marda Science LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# utility to merge multiple coincident jpeg images into nd numpy arrays
import os, json, shutil
from .imports import *

from natsort import natsorted
import numpy as np
from tkinter import filedialog
from tkinter import *
from glob import glob
from skimage.morphology import dilation, disk #remove_small_objects, remove_small_holes
from tqdm import tqdm
from joblib import Parallel, delayed
###===========================================

##========================================================
## USER INPUTS
##========================================================

root = Tk()
root.filename =  filedialog.askopenfilename(initialdir = os.getcwd(),title = "Select config file",filetypes = (("config files","*.json"),("all files","*.*")))
configfile = root.filename
print(configfile)
root.withdraw()

with open(configfile) as f:
    config = json.load(f)

for k in config.keys():
    exec(k+'=config["'+k+'"]')

USE_GPU = True
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

if USE_GPU == True:
    if 'SET_GPU' in locals():
        os.environ['CUDA_VISIBLE_DEVICES'] = str(SET_GPU)
    else:
        #use the first available GPU
        os.environ['CUDA_VISIBLE_DEVICES'] = '0' #'1'
else:
   ## to use the CPU (not recommended):
   os.environ['CUDA_VISIBLE_DEVICES'] = '-1'


root = Tk()
root.filename =  filedialog.askdirectory(initialdir = os.getcwd(),title = "Select directory for OUTPUT files")
output_data_path = root.filename
print(output_data_path)
root.withdraw()


root = Tk()
root.filename =  filedialog.askdirectory(initialdir = output_data_path,title = "Select directory of LABEL files")
label_data_path = root.filename
print(label_data_path)
root.withdraw()

root = Tk()
root.filename =  filedialog.askdirectory(initialdir = label_data_path,title = "Select directory of RGB IMAGE files")
data_path = root.filename
print(data_path)
root.withdraw()


W=[]
W.append(data_path)

root = Tk()
root.filename =  filedialog.askdirectory(initialdir = label_data_path,title = "Select directory of SWIR IMAGE files")
data_path = root.filename
print(data_path)
root.withdraw()
W.append(data_path)


##========================================================
## COLLATE FILES INTO LISTS
##========================================================

files = []
for data_path in W:
    f = natsorted(glob(data_path+os.sep+'*.jpg'))
    if len(f)<1:
        f = natsorted(glob(data_path+os.sep+'images'+os.sep+'*.jpg'))
    files.append(f)

# number of bands x number of samples
files = np.vstack(files).T

label_files = natsorted(glob(label_data_path+os.sep+'*.jpg'))
if len(label_files)<1:
    label_files = natsorted(glob(label_data_path+os.sep+'labels'+os.sep+'*.jpg'))


print("Found {} image and {} label files".format(len(files), len(label_files)))


##========================================================
## MAKING RESIZED COPIES OF IMAGERY
##========================================================

## make  direcs
for w in W:
    wend = w.split('/')[-1]
    newdirec = w.replace(wend,'resized_'+wend)

    try:
        os.mkdir(newdirec)
    except:
        pass

if USEMASK:
    newdireclabels = label_data_path.replace('mask','resized_mask')
else:
    newdireclabels = label_data_path.replace('label','resized_label')

# if directories already exist, skip them
if os.path.isdir(newdirec):#newdireclabels):
    print("{} already exists: skipping the image resizing step".format(newdirec))#newdireclabels))
else:

    try:
        os.mkdir(newdireclabels)
    except:
        pass

    if len(W)==1:
        try:
            w = Parallel(n_jobs=-2, verbose=0, max_nbytes=None)(delayed(do_resize_image)(os.path.normpath(f), TARGET_SIZE) for f in files)
        except:
            w = Parallel(n_jobs=-2, verbose=0, max_nbytes=None)(delayed(do_resize_image)(os.path.normpath(f), TARGET_SIZE) for f in files.squeeze())

        w = Parallel(n_jobs=-2, verbose=0, max_nbytes=None)(delayed(do_resize_label)(os.path.normpath(lfile), TARGET_SIZE) for lfile in label_files)

    else:
        ## cycle through, merge and padd/resize if need to
        for file,lfile in zip(files, label_files):

            for f in file:
                do_resize_image(f, TARGET_SIZE)
            do_resize_label(lfile, TARGET_SIZE)


## write padded labels to file
label_data_path = newdireclabels 

label_files = natsorted(glob(label_data_path+os.sep+'*.png'))
if len(label_files)<1:
    label_files = natsorted(glob(label_data_path+os.sep+'images'+os.sep+'*.png'))
print("{} label files".format(len(label_files)))

W2 = []
for w in W:
    wend = os.path.normpath(w).split(os.sep)[-1]
    w = w.replace(wend,'resized_'+wend)
    W2.append(w)
W = W2
del W2

files = []
for data_path in W:
    f = natsorted(glob(os.path.normpath(data_path)+os.sep+'*.png'))
    if len(f)<1:
        f = natsorted(glob(os.path.normpath(data_path)+os.sep+'images'+os.sep+'*.png'))
    files.append(f)

# number of bands x number of samples
files = np.vstack(files).T
print("{} sets of {} image files".format(len(W),len(files)))


##========================================================
## NON-AUGMENTED FILES
##========================================================


print("Creating non-augmented subset")
## make non-aug subset first
# cycle through pairs of files and labels
for counter,(f,l) in enumerate(zip(files,label_files)):

    g = imread(f[0])[:,:,1].astype('float')
    swir = imread(f[1]).astype('float')
    g[g==0]=np.nan
    swir[swir==0]=np.nan
    g = np.ma.filled(g)
    swir = np.ma.filled(swir)
    mndwi = np.divide(g - swir, g + swir )
    mndwi[np.isnan(mndwi)]=-1
    mndwi = rescale_array(mndwi,0,255)

    datadict={}
    try:
        datadict['arr_0'] = mndwi.astype(np.uint8)

        lab = imread(l) # reac the label

        if 'REMAP_CLASSES' in locals():
            for k in REMAP_CLASSES.items():
                lab[lab==int(k[0])] = int(k[1])

        lab[lab>NCLASSES]=NCLASSES

        if len(np.unique(lab))==1:
            nx,ny = lab.shape
            if NCLASSES==1:
                lstack = np.zeros((nx,ny,NCLASSES+1))
            else:
                lstack = np.zeros((nx,ny,NCLASSES))

            lstack[:,:,np.unique(lab)[0]]=np.ones((nx,ny))
        else:
            nx,ny = lab.shape
            if NCLASSES==1:
                lstack = np.zeros((nx,ny,NCLASSES+1))
                lstack[:,:,:NCLASSES+1] = (np.arange(NCLASSES+1) == 1+lab[...,None]-1).astype(int) #one-hot encode
            else:
                lstack = np.zeros((nx,ny,NCLASSES))
                lstack[:,:,:NCLASSES] = (np.arange(NCLASSES) == 1+lab[...,None]-1).astype(int) #one-hot encode

        if FILTER_VALUE>1:

            for kk in range(lstack.shape[-1]):
                # lab = remove_small_objects(lstack[:,:,kk].astype('uint8')>0, np.pi*(FILTER_VALUE**2))
                # lab = remove_small_holes(lstack[:,:,kk].astype('uint8')>0, np.pi*(FILTER_VALUE**2))
                lab = dilation(lstack[:,:,kk].astype('uint8')>0, disk(FILTER_VALUE))
                lstack[:,:,kk] = np.round(lab).astype(np.uint8)
                del lab

        datadict['arr_1'] = np.squeeze(lstack).astype(np.uint8)
        datadict['num_bands'] = 1
        datadict['files'] = [fi.split(os.sep)[-1] for fi in f]
        segfile = output_data_path+os.sep+ROOT_STRING+'_noaug_nd_data_000000'+str(counter)+'.npz'
        np.savez_compressed(segfile, **datadict)
        del datadict, lstack, mndwi
    except:
        print("Inconsistent inputs associated with label file: ".format(l))


###================================


#-----------------------------------
def load_npz(example):
    with np.load(example.numpy()) as data:
        image = data['arr_0'].astype('uint8')
        image = standardize(image)
        label = data['arr_1'].astype('uint8')
        try:
            file = [''.join(f) for f in data['files']]
        except:
            file = [f]
    return image, label, file[0]

@tf.autograph.experimental.do_not_convert
#-----------------------------------
def read_seg_dataset_multiclass(example):
    """
    "read_seg_dataset_multiclass(example)"
    This function reads an example from a npz file into a single image and label
    INPUTS:
        * dataset example object (filename of npz)
    OPTIONAL INPUTS: None
    GLOBAL INPUTS: TARGET_SIZE
    OUTPUTS:
        * image [tensor array]
        * class_label [tensor array]
    """
    image, label, file = tf.py_function(func=load_npz, inp=[example], Tout=[tf.float32, tf.uint8, tf.string])

    if NCLASSES==1:
        label = tf.expand_dims(label,-1)

    return image, label, file

###================================

##========================================================
## READ, VERIFY and PLOT NON-AUGMENTED FILES
##========================================================

# to deal with non-resized imaegry
BATCH_SIZE = 1

filenames = tf.io.gfile.glob(output_data_path+os.sep+ROOT_STRING+'_noaug*.npz')
dataset = tf.data.Dataset.list_files(filenames, shuffle=False)

print('{} files made'.format(len(filenames)))

# Set `num_parallel_calls` so multiple images are loaded/processed in parallel.
dataset = dataset.map(read_seg_dataset_multiclass, num_parallel_calls=AUTO)
dataset = dataset.repeat()
dataset = dataset.batch(BATCH_SIZE, drop_remainder=True) # drop_remainder will be needed on TPU
dataset = dataset.prefetch(AUTO)

try:
    os.mkdir(output_data_path+os.sep+'noaug_sample')
except:
    pass

#blue,red, yellow,green, etc
class_label_colormap = ['#3366CC','#DC3912','#FF9900','#109618','#990099','#0099C6','#DD4477',
                        '#66AA00','#B82E2E', '#316395','#0d0887', '#46039f', '#7201a8',
                        '#9c179e', '#bd3786', '#d8576b', '#ed7953', '#fb9f3a', '#fdca26', '#f0f921']

if NCLASSES>1:
    class_label_colormap = class_label_colormap[:NCLASSES]
else:
    class_label_colormap = class_label_colormap[:NCLASSES+1]


print('.....................................')
print('Printing examples to file ...')

counter=0
for imgs,lbls,files in dataset.take(20):

  for count,(im,lab, file) in enumerate(zip(imgs, lbls, files)):

     im = rescale_array(im.numpy(), 0, 1)

     plt.imshow(im)

     lab = np.argmax(lab.numpy().squeeze(),-1)

     color_label = label_to_colors(np.squeeze(lab), tf.cast(im[:,:,0]==0,tf.uint8),
                                    alpha=128, colormap=class_label_colormap,
                                     color_class_offset=0, do_alpha=False)

     if NCLASSES==1:
         plt.imshow(color_label, alpha=0.5)#, vmin=0, vmax=NCLASSES)
     else:
         #lab = np.argmax(lab,-1)
         plt.imshow(color_label,  alpha=0.5)#, vmin=0, vmax=NCLASSES)

     file = file.numpy()

     plt.axis('off')
     plt.title(file)
     plt.savefig(output_data_path+os.sep+'noaug_sample'+os.sep+ ROOT_STRING + 'noaug_ex'+str(counter)+'.png', dpi=200, bbox_inches='tight')
     #counter +=1
     plt.close('all')
     counter += 1



##========================================================
## AUGMENTED FILES
##========================================================

print("Creating augmented files")

# we create two instances with the same arguments
data_gen_args = dict(featurewise_center=False,
                     featurewise_std_normalization=False,
                     rotation_range=AUG_ROT,
                     width_shift_range=AUG_WIDTHSHIFT,
                     height_shift_range=AUG_HEIGHTSHIFT,
                     fill_mode='reflect', #'nearest',
                     zoom_range=AUG_ZOOM,
                     horizontal_flip=AUG_HFLIP,
                     vertical_flip=AUG_VFLIP)

null_data_gen_args = dict(featurewise_center=False,
                     featurewise_std_normalization=False,
                     rotation_range=0,
                     width_shift_range=0,
                     height_shift_range=0,
                     fill_mode='reflect',
                     zoom_range=0,
                     horizontal_flip=False,
                     vertical_flip=False)

#get image dimensions
NX = TARGET_SIZE[0]
NY = TARGET_SIZE[1]

null_image_datagen = tf.keras.preprocessing.image.ImageDataGenerator(**null_data_gen_args)
mask_datagen = tf.keras.preprocessing.image.ImageDataGenerator(**data_gen_args)
null_mask_datagen = tf.keras.preprocessing.image.ImageDataGenerator(**null_data_gen_args)

# important that each band has the same image generator
image_datagen = tf.keras.preprocessing.image.ImageDataGenerator(**data_gen_args)


## put images in subfolders
for counter,w in enumerate(W):
    n_im = len(glob(w+os.sep+'*.png')+glob(w+os.sep+'*.jpg'))
    if n_im>0:
        try:
            os.mkdir(w+os.sep+'images')
        except:
            pass
        try:
            for file in glob(w+os.sep+'*.png'):
                shutil.move(file,w+os.sep+'images')
            for file in glob(w+os.sep+'*.jpg'):
                shutil.move(file,w+os.sep+'images')
        except:
            pass

    n_im = len(glob(w+os.sep+'images'+os.sep+'*.*'))


## put label images in subfolders
n_im = len(glob(label_data_path+os.sep+'*.png')+glob(label_data_path+os.sep+'*.jpg'))
if n_im>0:
    try:
        os.mkdir(label_data_path+os.sep+'images')
    except:
        pass

try:
    for file in glob(label_data_path+os.sep+'*.jpg'):
        shutil.move(file,label_data_path+os.sep+'images')
    for file in glob(label_data_path+os.sep+'*.png'):
        shutil.move(file,label_data_path+os.sep+'images')
except:
    pass
n_im = len(glob(label_data_path+os.sep+'images'+os.sep+'*.*'))


#### make training generators directly, and in advance
train_generators = []
null_train_generators = []
for counter,w in enumerate(W):
    print("folder: {}".format(w.split(os.sep)[-1]))
    img_generator = image_datagen.flow_from_directory(
        w,
        target_size=(NX, NY),
        batch_size=int(n_im/AUG_LOOPS),
        class_mode=None, seed=SEED, shuffle=False)

    null_img_generator = null_image_datagen.flow_from_directory(
            w,
            target_size=(NX, NY),
            batch_size=int(n_im/AUG_LOOPS),
            class_mode=None, seed=SEED, shuffle=False)

    print("folder: {}".format(label_data_path.split(os.sep)[-1]))
    #the seed must be the same as for the training set to get the same images
    mask_generator = mask_datagen.flow_from_directory(
            label_data_path,
            target_size=(NX, NY),
            batch_size=int(n_im/AUG_LOOPS),
            class_mode=None, seed=SEED, shuffle=False, color_mode="grayscale", interpolation="nearest")

    null_mask_generator = null_mask_datagen.flow_from_directory(
            label_data_path,
            target_size=(NX, NY),
            batch_size=int(n_im/AUG_LOOPS),
            class_mode=None, seed=SEED, shuffle=False, color_mode="grayscale", interpolation="nearest")

    train_generator = (pair for pair in zip(img_generator, mask_generator))
    train_generators.append([img_generator,mask_generator,train_generator])

    null_train_generator = (pair for pair in zip(null_img_generator, null_mask_generator))
    null_train_generators.append([null_img_generator, null_mask_generator,null_train_generator])

######################## generate and print files

i = 0
for copy in tqdm(range(AUG_COPIES)):
    for k in range(AUG_LOOPS):
        # print("Working on copy number {} out of {}".format(copy,AUG_COPIES))
        # print("Working on loop {} out of {}".format(k,AUG_LOOPS))
        # print("Starting from augmented sample {}".format(i))

        # first band of rgb (g) and only band of swir
        X=[]; Y=[]; F=[]
        for counter,train_generator in enumerate(train_generators):
            #grab a batch of images and label images
            x, y = next(train_generator[-1])

            if counter==0:
                x = x[:,:,:,1].astype('float')
                x[x==0]=np.nan
                x = np.ma.filled(x)
            else:
                x = x[:,:,:,0].astype('float')
                x[x==0]=np.nan
                x = np.ma.filled(x)                

            idx = np.maximum((train_generator[0].batch_index - 1) * train_generator[0].batch_size, 0)
            filenames = train_generator[0].filenames[idx : idx + train_generator[0].batch_size]
            X.append(x)
            del x
            Y.append(y)
            del y
            F.append(filenames)
            del filenames

        mndwi = np.divide(X[1] - X[0], X[1] + X[0])
        mndwi[np.isnan(mndwi)]=-1
        mndwi = rescale_array(mndwi,0,255)
        del X

        ## for 1-band inputs, the generator will make 3-band inputs
        ## this is so
        ## that means for 3+ band inputs where the extra files encode just 1 band each
        ## single bands are triplicated and the following code removes the redundancy
        ## so check for bands 0 and 1 being the same and if so, use only bans 0
        X3 = []
        for x in mndwi:
            X3.append(np.dstack((x,x,x)))
        del mndwi

        Y = Y[0]
        # wrute them to file and increment the counter
        for counter,lab in enumerate(Y):

            im = X3[counter] #np.dstack([x[counter] for x in X3])

            files = np.dstack([x[counter] for x in F])

            ##============================================ label
            if NCLASSES==1:
                lab=lab.squeeze()
                lab[lab>0]=1

            if NCLASSES==1:
                l = lab.astype(np.uint8)
            else:
                l = np.round(lab[:,:,0]).astype(np.uint8)

            if 'REMAP_CLASSES' in locals():
                for k in REMAP_CLASSES.items():
                    l[l==int(k[0])] = int(k[1])

            l[l>NCLASSES]=NCLASSES

            if len(np.unique(l))==1:
                nx,ny = l.shape
                if NCLASSES==1:
                    lstack = np.zeros((nx,ny,NCLASSES+1))
                else:
                    lstack = np.zeros((nx,ny,NCLASSES))

                lstack[:,:,np.unique(l)[0]]=np.ones((nx,ny))
            else:
                nx,ny = l.shape
                if NCLASSES==1:
                    lstack = np.zeros((nx,ny,NCLASSES+1))
                    lstack[:,:,:NCLASSES+1] = (np.arange(NCLASSES+1) == 1+l[...,None]-1).astype(int) #one-hot encode
                else:
                    lstack = np.zeros((nx,ny,NCLASSES))
                    lstack[:,:,:NCLASSES] = (np.arange(NCLASSES) == 1+l[...,None]-1).astype(int) #one-hot encode

            if FILTER_VALUE>1:

                for kk in range(lstack.shape[-1]):
                    l = dilation(lstack[:,:,kk].astype('uint8')>0, disk(FILTER_VALUE))
                    lstack[:,:,kk] = np.round(l).astype(np.uint8)
                    del l

            datadict={}
            datadict['arr_0'] = im.astype(np.uint8)
            datadict['arr_1'] =  np.squeeze(lstack).astype(np.uint8)
            datadict['num_bands'] = im.shape[-1]
            try:
                datadict['files'] = [fi.split(os.sep)[-1] for fi in files.squeeze()]
            except:
                datadict['files'] = [files]

            np.savez_compressed(output_data_path+os.sep+ROOT_STRING+'_aug_nd_data_000000'+str(i),
                                **datadict)

            del lstack, im


            i += 1


##========================================================
## READ, VERIFY and PLOT AUGMENTED FILES
##========================================================

filenames = tf.io.gfile.glob(output_data_path+os.sep+ROOT_STRING+'_aug*.npz')
dataset = tf.data.Dataset.list_files(filenames, shuffle=False)

print('{} files made'.format(len(filenames)))

# Set `num_parallel_calls` so multiple images are loaded/processed in parallel.
dataset = dataset.map(read_seg_dataset_multiclass, num_parallel_calls=AUTO)
dataset = dataset.repeat()
dataset = dataset.batch(BATCH_SIZE, drop_remainder=True) # drop_remainder will be needed on TPU
dataset = dataset.prefetch(AUTO)

try:
    os.mkdir(output_data_path+os.sep+'aug_sample')
except:
    pass


print('.....................................')
print('Printing examples to file ...')

counter=0
for imgs,lbls,files in dataset.take(20):

  for count,(im,lab, file) in enumerate(zip(imgs, lbls, files)):

     im = rescale_array(im.numpy(), 0, 1)

     plt.imshow(im)

     lab = np.argmax(lab.numpy().squeeze(),-1)

     color_label = label_to_colors(np.squeeze(lab), tf.cast(im[:,:,0]==0,tf.uint8),
                                    alpha=128, colormap=class_label_colormap,
                                     color_class_offset=0, do_alpha=False)

     if NCLASSES==1:
         plt.imshow(color_label, alpha=0.5)#, vmin=0, vmax=NCLASSES)
     else:
         plt.imshow(color_label,  alpha=0.5)#, vmin=0, vmax=NCLASSES)

     try:
         file = file.numpy()
         plt.title(file)
         del file
     except:
         pass

     plt.axis('off')

     plt.savefig(output_data_path+os.sep+'aug_sample'+os.sep+ ROOT_STRING + 'aug_ex'+str(counter)+'.png', dpi=200, bbox_inches='tight')
     plt.close('all')
     counter += 1



#boom.
