# -*- coding: utf-8 -*-
"""creation (1).ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1OhX5kG16F2L1y3WqQgwkVkAu2GBtwiPt
"""

!wget https://os.unil.cloud.switch.ch/fma/fma_large.zip

!7z x fma_large.zip -o./fma_large

!wget https://os.unil.cloud.switch.ch/fma/fma_metadata.zip

!7z x fma_metadata.zip

!cp -R ./fma_metadata ./

!pip install python-dotenv

import os
import ast
import pickle
import IPython.display as ipd
import numpy as np
import pandas as pd
import dotenv
import pydot
import requests
import utils
import creation

"""# [FMA: A Dataset For Music Analysis](https://github.com/mdeff/fma)

Michaël Defferrard, Kirell Benzi, Pierre Vandergheynst, Xavier Bresson, EPFL LTS2.

## Creation

From `raw_*.csv`, this notebook generates:
* `tracks.csv`: per-track / album / artist metadata.
* `genres.csv`: genre hierarchy.
* `echonest.csv`: cleaned Echonest features.

A companion script, [creation.py](creation.py):
1. Query the [API](https://freemusicarchive.org/api) and store metadata in `raw_tracks.csv`, `raw_albums.csv`, `raw_artists.csv` and `raw_genres.csv`.
2. Download the audio for each track.
3. Trim the audio to 30s clips.
4. Normalize the permissions and modification / access times.
5. Create the `.zip` archives.
"""

AUDIO_DIR = '/content/fma_large/fma_large'
BASE_DIR = os.path.abspath(os.path.dirname(AUDIO_DIR))

"""Load the **CSV** files into pandas dataframe to extract details of tracks, albums, artists and generes. And also the pickle file that contains all of the metadata related to this dataset for training the model."""

# converters={'genres': ast.literal_eval}
tracks = pd.read_csv('/content/fma_metadata/raw_tracks.csv', index_col=0)
albums = pd.read_csv('/content/fma_metadata/raw_albums.csv', index_col=0)
artists = pd.read_csv('/content/fma_metadata/raw_artists.csv', index_col=0)
genres = pd.read_csv('/content/fma_metadata/raw_genres.csv', index_col=0)

not_found = pickle.load(open('./fma_metadata/not_found.pickle', 'rb'))

len(not_found)

for i in not_found:
  print(f'''{i}: {len(not_found[i])}''')

def get_fs_tids(audio_dir):
    tids = []
    for _, dirnames, files in os.walk(audio_dir):
        if dirnames == []:
            tids.extend(int(file[:-4]) for file in files)
    return tids

audio_tids = get_fs_tids("fma_small/fma_small")

print('tracks: {} collected ({} not found, {} max id)'.format(
    len(tracks), len(not_found['tracks']), tracks.index.max()))
print('albums: {} collected ({} not found, {} in tracks)'.format(
    len(albums), len(not_found['albums']), len(tracks['album_id'].unique())))
print('artists: {} collected ({} not found, {} in tracks)'.format(
    len(artists), len(not_found['artists']), len(tracks['artist_id'].unique())))
print('genres: {} collected'.format(len(genres)))
print('audio: {} collected ({} not found, {} not in tracks)'.format(
    len(audio_tids), len(not_found['audio']), len(set(audio_tids).difference(tracks.index))))
# assert sum(tracks.index.isin(audio_tids)) + len(not_found['audio']) == len(tracks)

N = 5
ipd.display(tracks.head(N))
ipd.display(albums.head(N))
ipd.display(artists.head(N))
ipd.display(genres.head(N))

df, column = tracks, 'tags'
null = sum(df[column].isnull())
print('{} null, {} non-null'.format(null, df.shape[0] - null))
df[column].value_counts().head(10)

"""### 2.1 Tracks"""

drop = [
    'license_image_file', 'license_image_file_large', 'license_parent_id', 'license_url',  # keep title only
    'track_file', 'track_image_file',  # used to download only
    'track_url', 'album_url', 'artist_url',  # only relevant on website
    'track_copyright_c', 'track_copyright_p',  # present for ~1000 tracks only
    # 'track_composer', 'track_lyricist', 'track_publisher',  # present for ~4000, <1000 and <2000 tracks
    'track_disc_number',  # different from 1 for <1000 tracks
    'track_explicit', 'track_explicit_notes',  # present for <4000 tracks
    'track_instrumental'  # ~6000 tracks have a 1, there is an instrumental genre
]
tracks.drop(drop, axis=1, inplace=True)
tracks.rename(columns={'license_title': 'track_license', 'tags': 'track_tags'}, inplace=True)

tracks['track_duration'] = tracks['track_duration'].map(creation.convert_duration)

def convert_datetime(df, column, format=None):
    df[column] = pd.to_datetime(df[column], infer_datetime_format=True, format=format)
convert_datetime(tracks, 'track_date_created')
convert_datetime(tracks, 'track_date_recorded')

tracks['album_id'].fillna(-1, inplace=True)
tracks['track_bit_rate'].fillna(-1, inplace=True)
tracks = tracks.astype({'album_id': int, 'track_bit_rate': int})

def convert_genres(genres):
    genres = ast.literal_eval(genres)
    return [int(genre['genre_id']) for genre in genres]

tracks['track_genres'].fillna('[]', inplace=True)
tracks['track_genres'] = tracks['track_genres'].map(convert_genres)

tracks.columns

"""### 2.2 Albums"""

drop = [
    'artist_name', 'album_url', 'artist_url',  # in tracks already (though it can be different)
    'album_handle',
    'album_image_file', 'album_images',  # todo: shall be downloaded
    #'album_producer', 'album_engineer',  # present for ~2400 albums only
]
albums.drop(drop, axis=1, inplace=True)
albums.rename(columns={'tags': 'album_tags'}, inplace=True)

convert_datetime(albums, 'album_date_created')
convert_datetime(albums, 'album_date_released')

albums.columns

"""### 2.3 Artists"""

drop = [
    'artist_website', 'artist_url',  # in tracks already (though it can be different)
    'artist_handle',
    'artist_image_file', 'artist_images',  # todo: shall be downloaded
    'artist_donation_url', 'artist_paypal_name', 'artist_flattr_name',  # ~1600 & ~400 & ~70, not relevant
    'artist_contact',  # ~1500, not very useful data
    # 'artist_active_year_begin', 'artist_active_year_end',  # ~1400, ~500 only
    # 'artist_associated_labels',  # ~1000
    # 'artist_related_projects',  # only ~800, but can be combined with bio
]
artists.drop(drop, axis=1, inplace=True)
artists.rename(columns={'tags': 'artist_tags'}, inplace=True)

convert_datetime(artists, 'artist_date_created')
for column in ['artist_active_year_begin', 'artist_active_year_end']:
    artists[column].replace(0.0, np.nan, inplace=True)
    convert_datetime(artists, column, format='%Y.0')

artists.columns

"""### 2.4 Merge DataFrames"""

not_found['albums'].remove(None)
not_found['albums'].append(-1)
not_found['albums'] = [int(i) for i in not_found['albums']]
not_found['artists'] = [int(i) for i in not_found['artists']]

tracks = tracks.merge(albums, left_on='album_id', right_index=True, sort=False, how='left', suffixes=('', '_dup'))

n = sum(tracks['album_title_dup'].isnull())
print('{} tracks without extended album information ({} tracks without album_id)'.format(
    n, sum(tracks['album_id'] == -1)))
assert sum(tracks['album_id'].isin(not_found['albums'])) == n
assert sum(tracks['album_title'] != tracks['album_title_dup']) == n

tracks.drop('album_title_dup', axis=1, inplace=True)
assert not any('dup' in col for col in tracks.columns)

tracks = tracks.merge(artists, left_on='artist_id', right_index=True, sort=False, how='left', suffixes=('', '_dup'))

n = sum(tracks['artist_name_dup'].isnull())
print('{} tracks without extended artist information'.format(n))
assert sum(tracks['artist_id'].isin(not_found['artists'])) == n
assert sum(tracks['artist_name'] != tracks[('artist_name_dup')]) == n

tracks.drop('artist_name_dup', axis=1, inplace=True)
assert not any('dup' in col for col in tracks.columns)

columns = []
for name in tracks.columns:
    names = name.split('_')
    columns.append((names[0], '_'.join(names[1:])))
tracks.columns = pd.MultiIndex.from_tuples(columns)
assert all(label in ['track', 'album', 'artist'] for label in tracks.columns.get_level_values(0))

# Todo: fill other columns ?
tracks['album', 'tags'].fillna('[]', inplace=True)
tracks['artist', 'tags'].fillna('[]', inplace=True)

columns = [('album', 'favorites'), ('album', 'comments'), ('album', 'listens'), ('album', 'tracks'),
           ('artist', 'favorites'), ('artist', 'comments')]
for column in columns:
    tracks[column].fillna(-1, inplace=True)
columns = {column: int for column in columns}
tracks = tracks.astype(columns)

"""## 3 Data cleaning

Todo: duplicates (metadata and audio)
"""

def keep(index, df):
    old = len(df)
    df = df.loc[index]
    new = len(df)
    print('{} lost, {} left'.format(old - new, new))
    return df

tracks = keep(tracks.index, tracks)

# Audio not found or could not be trimmed.
tracks = keep(tracks.index.difference(not_found['audio']), tracks)
tracks = keep(tracks.index.difference(not_found['clips']), tracks)

# Feature extraction failed.
FAILED = [1440, 26436, 28106, 29166, 29167, 29168, 29169, 29170, 29171, 29172,
          29173, 29179, 38903, 43903, 56757, 57603, 59361, 62095, 62954, 62956,
          62957, 62959, 62971, 75461, 80015, 86079, 92345, 92346, 92347, 92348,
          92349, 92350, 92351, 92352, 92353, 92354, 92355, 92356, 92357, 92358,
          92359, 92360, 92361, 96426, 104623, 106719, 109714, 114448, 114501,114528,
          115235, 117759, 118003, 118004, 127827, 130296, 130298, 131076, 135804, 136486,
          144769, 144770, 144771, 144773, 144774, 144775, 144776, 144777, 144778, 152204,
          154923]
tracks = keep(tracks.index.difference(FAILED), tracks)

# License forbids redistribution.
tracks = keep(tracks['track', 'license'] != 'FMA-Limited: Download Only', tracks)
print('{} licenses'.format(len(tracks[('track', 'license')].unique())))

#sum(tracks['track', 'title'].duplicated())

"""## 4 Genres"""

genres.drop(['genre_handle', 'genre_color'], axis=1, inplace=True)
genres.rename(columns={'genre_parent_id': 'parent', 'genre_title': 'title'}, inplace=True)

genres['parent'].fillna(0, inplace=True)
genres = genres.astype({'parent': int})

# 13 (Easy Listening) has parent 126 which is missing
# --> a root genre on the website, although not in the genre menu
genres.at[13, 'parent'] = 0

# 580 (Abstract Hip-Hop) has parent 1172 which is missing
# --> listed as child of Hip-Hop on the website
genres.at[580, 'parent'] = 21

# 810 (Nu-Jazz) has parent 51 which is missing
# --> listed as child of Easy Listening on website
genres.at[810, 'parent'] = 13

# 763 (Holiday) has parent 763 which is itself
# --> listed as child of Sound Effects on website
genres.at[763, 'parent'] = 16

# Todo: should novelty be under Experimental? It is alone on website.

# Genre 806 (hiphop) should not exist. Replace it by 21 (Hip-Hop).
print('{} tracks have genre 806'.format(
    sum(tracks['track', 'genres'].map(lambda genres: 806 in genres))))
def change_genre(genres):
    return [genre if genre != 806 else 21 for genre in genres]
tracks['track', 'genres'] = tracks['track', 'genres'].map(change_genre)
genres.drop(806, inplace=True)

def get_parent(genre, track_all_genres=None):
    parent = genres.at[genre, 'parent']
    if track_all_genres is not None:
        track_all_genres.append(genre)
    return genre if parent == 0 else get_parent(parent, track_all_genres)

# Get all genres, i.e. all genres encountered when walking from leafs to roots.
def get_all_genres(track_genres):
    track_all_genres = list()
    for genre in track_genres:
        get_parent(genre, track_all_genres)
    return list(set(track_all_genres))

tracks['track', 'genres_all'] = tracks['track', 'genres'].map(get_all_genres)

# Number of tracks per genre.
def count_genres(subset=tracks.index):
    count = pd.Series(0, index=genres.index)
    for _, track_all_genres in tracks.loc[subset, ('track', 'genres_all')].items():
        for genre in track_all_genres:
            count[genre] += 1
    return count

genres['#tracks'] = count_genres()
genres[genres['#tracks'] == 0]

def get_top_genre(track_genres):
    top_genres = set(genres.at[genres.at[genre, 'top_level'], 'title'] for genre in track_genres)
    return top_genres.pop() if len(top_genres) == 1 else np.nan

# Top-level genre.
genres['top_level'] = genres.index.map(get_parent)
tracks['track', 'genre_top'] = tracks['track', 'genres'].map(get_top_genre)

genres.head(161)

"""### 5.3 Small

Main characteristic: genre balanced (and echonest features).

Choices:
* 8 genres with 1000 tracks --> 8,000 tracks
* 10 genres with 500 tracks --> 5,000 tracks

Todo:
* Download more echonest features so that all tracks can have them. Otherwise intersection of tracks with echonest features and one top-level genre is too small.
"""

N_GENRES = 8
N_TRACKS = 1000

"""### 5.4 Subset indication"""

from pandas.api.types import CategoricalDtype

SUBSETS = ['small']
cat_dtype = CategoricalDtype(categories=SUBSETS, ordered=True)

tracks['set', 'subset'] = pd.Series().astype(cat_dtype)

fma_small = pd.DataFrame(tracks)
tracks.loc[fma_small.index, ('set', 'subset')] = 'small'

"""### 5.5 Echonest"""

echonest = pd.read_csv('./fma_metadata/raw_echonest.csv', index_col=0, header=[0, 1, 2])
echonest = keep(~echonest['echonest', 'temporal_features'].isnull().any(axis=1), echonest)
echonest = keep(~echonest['echonest', 'audio_features'].isnull().any(axis=1), echonest)
echonest = keep(~echonest['echonest', 'social_features'].isnull().any(axis=1), echonest)

echonest = keep(echonest.index.isin(tracks.index), echonest);
keep(echonest.index.isin(fma_large.index), echonest);

"""## 6 Splits: training, validation, test

Take into account:
* Artists may only appear on one side.
* Stratification: ideally, all characteristics (#tracks per artist, duration, sampling rate, information, bio) and targets (genres, tags) should be equally distributed.
"""

from pandas.api.types import CategoricalDtype
import numpy as np

for genre in genres.index:
    tracks['genre', genres.at[genre, 'title']] = tracks['track', 'genres_all'].map(lambda genres: genre in genres)

SPLITS = ('training', 'test', 'validation')
PERCENTAGES = (0.8, 0.1, 0.1)

cat_type = CategoricalDtype(categories=SPLITS, ordered=True)
tracks['set', 'split'] = pd.Series().astype(cat_type)

for subset in SUBSETS:

    tracks_subset = tracks['set', 'subset'] <= subset

    genre_list = list(tracks.loc[tracks_subset, ('track', 'genre_top')].unique())
    genre_list = [genre for genre in genre_list if genre == genre]  # Exclude 'nan' values

    if subset == 'large':
        genre_list = list(genres['title'])

    while True:
        if len(genre_list) == 0:
            break

        tracks_unsplit = tracks['set', 'split'].isnull()
        count = tracks[tracks_subset & tracks_unsplit].set_index(('artist', 'id'), append=True)['genre']
        count = count.groupby(level=1).sum().astype(np.bool).sum()

        # Instead of getting the genre from `count` by its index, get it directly from `genre_list`
        genre_index = np.argmin(count[genre_list])
        genre = genre_list[genre_index]
        genre_list.remove(genre)

        tracks_genre = tracks['genre', genre] == 1
        artists = tracks.loc[tracks_genre & tracks_subset & tracks_unsplit, ('artist', 'id')].value_counts()

        current = {split: np.sum(tracks_genre & tracks_subset & (tracks['set', 'split'] == split)) for split in SPLITS}

        for artist, count in artists.items():
            choice = np.argmin([current[split] / percentage for split, percentage in zip(SPLITS, PERCENTAGES)])
            current[SPLITS[choice]] += count
            tracks.loc[tracks['artist', 'id'] == artist, ('set', 'split')] = SPLITS[choice]

no_genres = tracks['track', 'genres_all'].map(lambda genres: len(genres) == 0)
no_split = tracks['set', 'split'].isnull()
assert not (no_split & ~no_genres).any()
tracks.loc[no_split, ('set', 'split')] = 'training'

tracks.drop('genre', axis=1, level=0, inplace=True)

"""## 7 Store"""

for dataset in 'tracks', 'genres', 'echonest':
    eval(dataset).sort_index(axis=0, inplace=True)
    eval(dataset).sort_index(axis=1, inplace=True)
    params = dict(float_format='%.10f') if dataset == 'echonest' else dict()
    eval(dataset).to_csv(dataset + '.csv', **params)

# ./creation.py normalize /path/to/fma
# ./creation.py zips /path/to/fma

"""## 8 Description"""

tracks = utils.load('./fma_metadata/tracks.csv')
tracks.dtypes

N = 5
ipd.display(tracks['track'].head(N))
ipd.display(tracks['album'].head(N))
ipd.display(tracks['artist'].head(N))

pip install librosa

# Commented out IPython magic to ensure Python compatibility.
# %matplotlib inline

import os

import IPython.display as ipd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sklearn as skl
import sklearn.utils, sklearn.preprocessing, sklearn.decomposition, sklearn.svm
import librosa
import librosa.display

import utils

plt.rcParams['figure.figsize'] = (17, 5)

# Directory where mp3 are stored.
AUDIO_DIR = os.environ.get('./fma_small')

# Load metadata and features.
tracks = utils.load('./fma_metadata/tracks.csv')
genres = utils.load('./fma_metadata/genres.csv')
features = utils.load('./fma_metadata/features.csv')
echonest = utils.load('./fma_metadata/echonest.csv')

np.testing.assert_array_equal(features.index, tracks.index)
assert echonest.index.isin(tracks.index).all()

tracks.shape, genres.shape, features.shape, echonest.shape

ipd.display(tracks['track'].head())
ipd.display(tracks['album'].head())
ipd.display(tracks['artist'].head())
ipd.display(tracks['set'].head())

small = tracks[tracks['set', 'subset'] <= 'small']
small.shape

print('{} top-level genres'.format(len(genres['top_level'].unique())))
genres.loc[genres['top_level'].unique()].sort_values('#tracks', ascending=False)

genres.sort_values('#tracks').head(10)

print('{1} features for {0} tracks'.format(*features.shape))
columns = ['mfcc', 'chroma_cens', 'tonnetz', 'spectral_contrast']
columns.append(['spectral_centroid', 'spectral_bandwidth', 'spectral_rolloff'])
columns.append(['rmse', 'zcr'])
for column in columns:
    ipd.display(features[column].head().style.format('{:.2f}'))

print('{1} features for {0} tracks'.format(*echonest.shape))
ipd.display(echonest['echonest', 'metadata'].head())
ipd.display(echonest['echonest', 'audio_features'].head())
ipd.display(echonest['echonest', 'social_features'].head())
ipd.display(echonest['echonest', 'ranks'].head())

ipd.display(echonest['echonest', 'temporal_features'].head())
x = echonest.loc[2, ('echonest', 'temporal_features')]
plt.plot(x);

small = tracks['set', 'subset'] <= 'small'
genre1 = tracks['track', 'genre_top'] == 'Instrumental'
genre2 = tracks['track', 'genre_top'] == 'Hip-Hop'

X = features.loc[small & (genre1 | genre2), 'mfcc']
X = skl.decomposition.PCA(n_components=2).fit_transform(X)

y = tracks.loc[small & (genre1 | genre2), ('track', 'genre_top')]
y = skl.preprocessing.LabelEncoder().fit_transform(y)

plt.scatter(X[:,0], X[:,1], c=y, cmap='RdBu', alpha=0.5)
X.shape, y.shape

AUDIO_DIR = "./fma_small/fma_small"
filename = utils.get_audio_path(AUDIO_DIR, 2)
print('File: {}'.format(filename))

x, sr = librosa.load(filename, sr=None, mono=True)
print('Duration: {:.2f}s, {} samples'.format(x.shape[-1] / sr, x.size))

start, end = 7, 17
ipd.Audio(data=x[start*sr:end*sr], rate=sr)

!pip install librosa
import librosa

stft = np.abs(librosa.stft(x, n_fft=2048, hop_length=512))
mel = librosa.feature.melspectrogram(sr=sr, S=stft**2)

mfcc = librosa.feature.mfcc(S=librosa.power_to_db(mel), n_mfcc=20)
mfcc = skl.preprocessing.StandardScaler().fit_transform(mfcc)
librosa.display.specshow(mfcc, sr=sr, x_axis='time');

small = tracks['set', 'subset'] <= 'small'

train = tracks['set', 'split'] == 'training'
val = tracks['set', 'split'] == 'validation'
test = tracks['set', 'split'] == 'test'

y_train = tracks.loc[small & train, ('track', 'genre_top')]
y_test = tracks.loc[small & test, ('track', 'genre_top')]
X_train = features.loc[small & train, 'mfcc']
X_test = features.loc[small & test, 'mfcc']

print('{} training examples, {} testing examples'.format(y_train.size, y_test.size))
print('{} features, {} classes'.format(X_train.shape[1], np.unique(y_train).size))

# Be sure training samples are shuffled.
X_train, y_train = skl.utils.shuffle(X_train, y_train, random_state=42)

# Standardize features by removing the mean and scaling to unit variance.
scaler = skl.preprocessing.StandardScaler(copy=False)
scaler.fit_transform(X_train)
scaler.transform(X_test)

# Support vector classification.
clf = skl.svm.SVC()
clf.fit(X_train, y_train)
score = clf.score(X_test, y_test)
print('Accuracy: {:.2%}'.format(score))

import time
import os

import IPython.display as ipd
from tqdm import tqdm_notebook
import numpy as np
import pandas as pd
import keras
from keras.layers import Activation, Dense, Conv1D, Conv2D, MaxPooling1D, Flatten, Reshape

from sklearn.utils import shuffle
from sklearn.preprocessing import MultiLabelBinarizer, LabelEncoder, LabelBinarizer, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC, LinearSVC
#from sklearn.gaussian_process import GaussianProcessClassifier
#from sklearn.gaussian_process.kernels import RBF
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
from sklearn.multiclass import OneVsRestClassifier

import utils

AUDIO_DIR = os.environ.get('./fma_small/fma_small')

tracks = utils.load('./fma_metadata/tracks.csv')
features = utils.load('./fma_metadata/features.csv')
echonest = utils.load('./fma_metadata/echonest.csv')

np.testing.assert_array_equal(features.index, tracks.index)
assert echonest.index.isin(tracks.index).all()

tracks.shape, features.shape, echonest.shape

subset = tracks.index[tracks['set', 'subset'] <= 'medium']

assert subset.isin(tracks.index).all()
assert subset.isin(features.index).all()

features_all = features.join(echonest, how='inner').sort_index(axis=1)
print('Not enough Echonest features: {}'.format(features_all.shape))

tracks = tracks.loc[subset]
features_all = features.loc[subset]

tracks.shape, features_all.shape

train = tracks.index[tracks['set', 'split'] == 'training']
val = tracks.index[tracks['set', 'split'] == 'validation']
test = tracks.index[tracks['set', 'split'] == 'test']

print('{} training examples, {} validation examples, {} testing examples'.format(*map(len, [train, val, test])))

genres = list(LabelEncoder().fit(tracks['track', 'genre_top']).classes_)
#genres = list(tracks['track', 'genre_top'].unique())
print('Top genres ({}): {}'.format(len(genres), genres))
genres = list(MultiLabelBinarizer().fit(tracks['track', 'genres_all']).classes_)
print('All genres ({}): {}'.format(len(genres), genres))

def pre_process(tracks, features, columns, multi_label=False, verbose=False):
    if not multi_label:
        # Assign an integer value to each genre.
        enc = LabelEncoder()
        labels = tracks['track', 'genre_top']
        #y = enc.fit_transform(tracks['track', 'genre_top'])
    else:
        # Create an indicator matrix.
        enc = MultiLabelBinarizer()
        labels = tracks['track', 'genres_all']
        #labels = tracks['track', 'genres']

    # Split in training, validation and testing sets.
    y_train = enc.fit_transform(labels[train])
    y_val = enc.transform(labels[val])
    y_test = enc.transform(labels[test])
    X_train = features.loc[train, columns]
    X_val = features.loc[val, columns]
    X_test = features.loc[test, columns]

    X_train, y_train = shuffle(X_train, y_train, random_state=42)

    # Standardize features by removing the mean and scaling to unit variance.
    scaler = StandardScaler(copy=False)
    scaler.fit_transform(X_train)
    scaler.transform(X_val)
    scaler.transform(X_test)

    return y_train, y_val, y_test, X_train, X_val, X_test

def test_classifiers_features(classifiers, feature_sets, multi_label=False):
    columns = list(classifiers.keys()).insert(0, 'dim')
    scores = pd.DataFrame(columns=columns, index=feature_sets.keys())
    times = pd.DataFrame(columns=classifiers.keys(), index=feature_sets.keys())
    for fset_name, fset in tqdm_notebook(feature_sets.items(), desc='features'):
        y_train, y_val, y_test, X_train, X_val, X_test = pre_process(tracks, features_all, fset, multi_label)
        scores.loc[fset_name, 'dim'] = X_train.shape[1]
        for clf_name, clf in classifiers.items():  # tqdm_notebook(classifiers.items(), desc='classifiers', leave=False):
            t = time.process_time()
            clf.fit(X_train, y_train)
            score = clf.score(X_test, y_test)
            scores.loc[fset_name, clf_name] = score
            times.loc[fset_name, clf_name] = time.process_time() - t
    return scores, times

def format_scores(scores):
    def highlight(s):
        is_max = s == max(s[1:])
        return ['background-color: yellow' if v else '' for v in is_max]
    scores = scores.style.apply(highlight, axis=1)
    return scores.format('{:.2%}', subset=pd.IndexSlice[:, scores.columns[1]:])

!pip install --upgrade scikit-learn

classifiers = {
    'LR': LogisticRegression(),
    'kNN': KNeighborsClassifier(n_neighbors=200),
    'SVCrbf': SVC(kernel='rbf'),
    'SVCpoly1': SVC(kernel='poly', degree=1),
    'linSVC1': SVC(kernel="linear"),
    'linSVC2': LinearSVC(),
    #GaussianProcessClassifier(1.0 * RBF(1.0), warm_start=True),
    'DT': DecisionTreeClassifier(max_depth=5),
    'RF': RandomForestClassifier(max_depth=5, n_estimators=10, max_features=1),
    'AdaBoost': AdaBoostClassifier(n_estimators=10),
    'MLP1': MLPClassifier(hidden_layer_sizes=(100,), max_iter=2000),
    'MLP2': MLPClassifier(hidden_layer_sizes=(200, 50), max_iter=2000),
    'NB': GaussianNB(),
    'QDA': QuadraticDiscriminantAnalysis(),
}

feature_sets = {
#    'echonest_audio': ('echonest', 'audio_features'),
#    'echonest_social': ('echonest', 'social_features'),
#    'echonest_temporal': ('echonest', 'temporal_features'),
#    'echonest_audio/social': ('echonest', ('audio_features', 'social_features')),
#    'echonest_all': ('echonest', ('audio_features', 'social_features', 'temporal_features')),
}
for name in features.columns.levels[0]:
    feature_sets[name] = name
feature_sets.update({
    'mfcc/contrast': ['mfcc', 'spectral_contrast'],
    'mfcc/contrast/chroma': ['mfcc', 'spectral_contrast', 'chroma_cens'],
    'mfcc/contrast/centroid': ['mfcc', 'spectral_contrast', 'spectral_centroid'],
    'mfcc/contrast/chroma/centroid': ['mfcc', 'spectral_contrast', 'chroma_cens', 'spectral_centroid'],
    'mfcc/contrast/chroma/centroid/tonnetz': ['mfcc', 'spectral_contrast', 'chroma_cens', 'spectral_centroid', 'tonnetz'],
    'mfcc/contrast/chroma/centroid/zcr': ['mfcc', 'spectral_contrast', 'chroma_cens', 'spectral_centroid', 'zcr'],
    'all_non-echonest': list(features.columns.levels[0])
})

scores, times = test_classifiers_features(classifiers, feature_sets)

ipd.display(format_scores(scores))
ipd.display(times.style.format('{:.4f}'))

AUDIO_DIR = './fma_small/fma_small'

labels_onehot = LabelBinarizer().fit_transform(tracks['track', 'genre_top'])
labels_onehot = pd.DataFrame(labels_onehot, index=tracks.index)

utils.FfmpegLoader().load(utils.get_audio_path('./fma_small', 2))
SampleLoader = utils.build_sample_loader('./fma_small', labels_onehot, utils.FfmpegLoader())
SampleLoader(train, batch_size=2).__next__()[0].shape

NB_WORKER = len(os.sched_getaffinity(0))  # number of usables CPUs
params = {'pickle_safe': True, 'nb_worker': NB_WORKER, 'max_q_size': 10}

loader = utils.FfmpegLoader(sampling_rate=2000)
SampleLoader = utils.build_sample_loader('./fma_small', labels_onehot, loader)
print('Dimensionality: {}'.format(loader.shape))

keras.backend.clear_session()

model = keras.models.Sequential()
model.add(Dense(output_dim=1000, input_shape=loader.shape))
model.add(Activation("relu"))
model.add(Dense(output_dim=100))
model.add(Activation("relu"))
model.add(Dense(output_dim=labels_onehot.shape[1]))
model.add(Activation("softmax"))

optimizer = keras.optimizers.SGD(lr=0.1, momentum=0.9, nesterov=True)
model.compile(optimizer, loss='categorical_crossentropy', metrics=['accuracy'])

model.fit_generator(SampleLoader(train, batch_size=64), train.size, nb_epoch=20, **params)
loss = model.evaluate_generator(SampleLoader(val, batch_size=64), val.size, **params)
loss = model.evaluate_generator(SampleLoader(test, batch_size=64), test.size, **params)
#Y = model.predict_generator(SampleLoader(test, batch_size=64), test.size, **params);

model.save('./fully_connected_neural_network.h5')

loss

loader = utils.FfmpegLoader(sampling_rate=16000)
#loader = utils.LibrosaLoader(sampling_rate=16000)
SampleLoader = utils.build_sample_loader(AUDIO_DIR, labels_onehot, loader)

keras.backend.clear_session()

model = keras.models.Sequential()
model.add(Reshape((-1, 1), input_shape=loader.shape))
print(model.output_shape)

model.add(Conv1D(128, 512, subsample_length=512))
print(model.output_shape)
model.add(Activation("relu"))

model.add(Conv1D(32, 8))
print(model.output_shape)
model.add(Activation("relu"))
model.add(MaxPooling1D(4))

model.add(Conv1D(32, 8))
print(model.output_shape)
model.add(Activation("relu"))
model.add(MaxPooling1D(4))

print(model.output_shape)
#model.add(Dropout(0.25))
model.add(Flatten())
print(model.output_shape)
model.add(Dense(100))
model.add(Activation("relu"))
print(model.output_shape)
model.add(Dense(labels_onehot.shape[1]))
model.add(Activation("softmax"))
print(model.output_shape)

optimizer = keras.optimizers.SGD(lr=0.01, momentum=0.9, nesterov=True)
#optimizer = keras.optimizers.Adam()#lr=1e-5)#, momentum=0.9, nesterov=True)
model.compile(optimizer, loss='categorical_crossentropy', metrics=['accuracy'])

model.fit_generator(SampleLoader(train, batch_size=10), train.size, nb_epoch=20, **params)
loss = model.evaluate_generator(SampleLoader(val, batch_size=10), val.size, **params)
loss = model.evaluate_generator(SampleLoader(test, batch_size=10), test.size, **params)

model.save('./convolutional_neural_network.h5')

loss