import os
from google.cloud import storage
import json
import io
from google.cloud import speech_v1
from google.cloud.speech_v1 import enums
from google.cloud.speech_v1 import types
import subprocess
from pydub.utils import mediainfo
import subprocess
import math
import datetime
import srt
import base64
import pywav
import requests
from pydub import AudioSegment

os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="speechcaption-73406c9ba1ee.json"


BUCKET_NAME = "speechaskai" # update this with your bucket name

def load_srt(filename):
    # load original .srt file
    # parse .srt file to list of subtitles
    print("Loading {}".format(filename))
    with open(filename) as f:
        text = f.read()
    return list(srt.parse(text))


def write_txt(subs):
    txt_file = "logs.txt"
    f = open(txt_file, 'w')
    for sub in subs:
        f.write(sub.content.replace("\n", " ") + '\n')
    f.close()
    print("Wrote text file {}".format(txt_file))
    return



def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    # bucket_name = "your-bucket-name"
    # source_file_name = "local/path/to/file"
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    print(
        "File {} uploaded to {}.".format(
            source_file_name, destination_blob_name
        )
    )

def video_info(video_filepath):
    """ this function returns number of channels, bit rate, and sample rate of the video"""

    video_data = mediainfo(video_filepath)
    channels = video_data["channels"]
    bit_rate = video_data["bit_rate"]
    sample_rate = video_data["sample_rate"]
    print("sample rate = "+ channels)
    return channels, bit_rate, sample_rate

def video_to_audio(video_filepath, audio_filename, video_channels, video_bit_rate, video_sample_rate):
    audio = AudioSegment.from_file("indian.mp4", format="mp4")
    audio.export(audio_filename, format="wav")
    #command = f"ffmpeg -i {video_filepath} -b:a {video_bit_rate} -ac {video_channels} -ar {video_sample_rate} -vn {audio_filename}"
    #subprocess.call(command, shell=True)
    blob_name = f"audios/{audio_filename}"
    #wave_read = pywav.WavRead(audio_filename)
    #print(wave_read.getparams())
    # Audio format 1 = PCM (without compression)
    # Audio format 6 = PCMA (with A-law compression)
    # Audio format 7 = PCMU (with mu-law compression)
    #wave_write = pywav.WavWrite("comp.wav", video_channels, video_sample_rate, video_bit_rate, 6)
    #wave_write.close()
    upload_blob(BUCKET_NAME, audio_filename, blob_name)
    return blob_name
    #return audio_filename



# Pass the audio data to an encoding function.
def delete_blob(bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    # bucket_name = "your-bucket-name"
    # blob_name = "your-object-name"

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()

    print("Blob {} deleted.".format(blob_name))


def long_running_recognize(storage_uri, channels, sample_rate):

    client = speech_v1.SpeechClient()

    config = {
        "language_code": "en-IN",
        "sample_rate_hertz": int(sample_rate),
        "encoding": enums.RecognitionConfig.AudioEncoding.LINEAR16,
        "audio_channel_count": int(channels),
        "enable_word_time_offsets": True,
        "enable_automatic_punctuation":True
    }

    audio = {"uri": storage_uri}
    #with io.open(storage_uri, "rb") as f:
    #    content = f.read()
    #audio = {"content": content}

    operation = client.long_running_recognize(config, audio)

    print(u"Waiting for operation to complete...")
    response = operation.result()
    return response

def subtitle_generation(speech_to_text_response, bin_size=3):
    """We define a bin of time period to display the words in sync with audio.
    Here, bin_size = 3 means each bin is of 3 secs.
    All the words in the interval of 3 secs in result will be grouped togather."""
    transcriptions = []
    index = 0

    for result in response.results:
        try:
            if result.alternatives[0].words[0].start_time.seconds:
                # bin start -> for first word of result
                start_sec = result.alternatives[0].words[0].start_time.seconds
                start_microsec = result.alternatives[0].words[0].start_time.nanos * 0.001
            else:
                # bin start -> For First word of response
                start_sec = 0
                start_microsec = 0
            end_sec = start_sec + bin_size # bin end sec

            # for last word of result
            last_word_end_sec = result.alternatives[0].words[-1].end_time.seconds
            last_word_end_microsec = result.alternatives[0].words[-1].end_time.nanos * 0.001

            # bin transcript
            transcript = result.alternatives[0].words[0].word

            index += 1 # subtitle index

            for i in range(len(result.alternatives[0].words) - 1):
                try:
                    word = result.alternatives[0].words[i + 1].word
                    word_start_sec = result.alternatives[0].words[i + 1].start_time.seconds
                    word_start_microsec = result.alternatives[0].words[i + 1].start_time.nanos * 0.001 # 0.001 to convert nana -> micro
                    word_end_sec = result.alternatives[0].words[i + 1].end_time.seconds
                    word_end_microsec = result.alternatives[0].words[i + 1].end_time.nanos * 0.001

                    if word_end_sec < end_sec:
                        transcript = transcript + " " + word
                    else:
                        previous_word_end_sec = result.alternatives[0].words[i].end_time.seconds
                        previous_word_end_microsec = result.alternatives[0].words[i].end_time.nanos * 0.001

                        # append bin transcript
                        transcriptions.append(srt.Subtitle(index, datetime.timedelta(0, start_sec, start_microsec), datetime.timedelta(0, previous_word_end_sec, previous_word_end_microsec), transcript))

                        # reset bin parameters
                        start_sec = word_start_sec
                        start_microsec = word_start_microsec
                        end_sec = start_sec + bin_size
                        transcript = result.alternatives[0].words[i + 1].word

                        index += 1
                except IndexError:
                    pass
            # append transcript of last transcript in bin
            transcriptions.append(srt.Subtitle(index, datetime.timedelta(0, start_sec, start_microsec), datetime.timedelta(0, last_word_end_sec, last_word_end_microsec), transcript))
            index += 1
        except IndexError:
            pass

    # turn transcription list into subtitles
    subtitles = srt.compose(transcriptions)
    return subtitles


print('Enter the Video file path')
path = input()
channels, bit_rate, sample_rate = video_info(path)
blob_name=video_to_audio(path, "audiospeech.wav", channels, bit_rate, sample_rate)
gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
print(gcs_uri)
response=long_running_recognize(gcs_uri, channels, sample_rate)
subtitles= subtitle_generation(response)
with open("subtitles.srt", "w") as f:
    f.write(subtitles)
delete_blob(BUCKET_NAME, blob_name)
subis = load_srt("subtitles.srt")
write_txt(subis)
