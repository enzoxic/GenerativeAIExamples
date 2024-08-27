"""
This demo script shows how to send audio data to Audio2Face Streaming Audio Player via gRPC requests.
There are two options:
 * Send the whole track at once using PushAudioRequest()
 * Send the audio chunks seuqntially in a stream using PushAudioStreamRequest()
For the second option this script emulates the stream of chunks, generated by splitting an input WAV audio file.
But in a real application such stream of chunks may be aquired from some other streaming source:
 * streaming audio via internet, streaming Text-To-Speech, etc
gRPC protocol details could be find in audio2face.proto
"""

import audio2face_pb2
import audio2face_pb2_grpc
import grpc
import numpy as np
import soundfile as sf


def push_audio_track(url, audio_data, samplerate, instance_name):
    """
    This function pushes the whole audio track at once via PushAudioRequest()
    PushAudioRequest parameters:
     * audio_data: bytes, containing audio data for the whole track, where each sample is encoded as 4 bytes (float32)
     * samplerate: sampling rate for the audio data
     * instance_name: prim path of the Audio2Face Streaming Audio Player on the stage, were to push the audio data
     * block_until_playback_is_finished: if True, the gRPC request will be blocked until the playback of the pushed track is finished
    The request is passed to PushAudio()
    """

    block_until_playback_is_finished = True  # ADJUSTABLE
    with grpc.insecure_channel(url) as channel:
        stub = audio2face_pb2_grpc.Audio2FaceStub(channel)
        request = audio2face_pb2.PushAudioRequest()
        request.audio_data = audio_data.astype(np.float32).tobytes()
        request.samplerate = samplerate
        request.instance_name = instance_name
        request.block_until_playback_is_finished = block_until_playback_is_finished
        print("Sending audio data...")
        response = stub.PushAudio(request)
        if not response.success:
            print(f"ERROR: {response.message}")

    print("Closed channel \n")

def audio_chunk_generator(resp):


    for i, rep in enumerate(resp):
        audio_samples = np.frombuffer(rep.audio, dtype=np.int16) / (2**15)

        # sf.write(f'output_audio_{i}.wav', audio_samples, 44100)
        # print("Chunk: ", i)
        yield audio_samples


def push_audio_track_stream(url, audio_chunk_generator, samplerate, instance_name):
    """
    This function pushes audio chunks sequentially via PushAudioStreamRequest()
    The function emulates the stream of chunks, generated by splitting input audio track.
    But in a real application such stream of chunks may be aquired from some other streaming source.
    The first message must contain start_marker field, containing only meta information (without audio data):
     * samplerate: sampling rate for the audio data
     * instance_name: prim path of the Audio2Face Streaming Audio Player on the stage, were to push the audio data
     * block_until_playback_is_finished: if True, the gRPC request will be blocked until the playback of the pushed track is finished (after the last message)
    Second and other messages must contain audio_data field:
     * audio_data: bytes, containing audio data for an audio chunk, where each sample is encoded as 4 bytes (float32)
    All messages are packed into a Python generator and passed to PushAudioStream()
    """

    chunk_size = samplerate // 2  # ADJUSTABLE
    block_until_playback_is_finished = True  # ADJUSTABLE


    with grpc.insecure_channel(url, options=[
        ('grpc.default_call_options.timeout', 15),
    ]) as channel:
        print("\nChannel created")
        stub = audio2face_pb2_grpc.Audio2FaceStub(channel)

        def make_generator():
            print(instance_name)
            start_marker = audio2face_pb2.PushAudioRequestStart(
                samplerate=samplerate,
                instance_name=instance_name,
                block_until_playback_is_finished=block_until_playback_is_finished,
            )
            # At first, we send a message with start_marker
            yield audio2face_pb2.PushAudioStreamRequest(start_marker=start_marker)
            # Then we send messages with audio_data


            for chunk in audio_chunk_generator:
                yield audio2face_pb2.PushAudioStreamRequest(audio_data=chunk.astype(np.float32).tobytes())

        request_generator = make_generator()
        print("Sending audio data to audio2face...")
        response = stub.PushAudioStream(request_generator)
        if response.success:
            print("SUCCESS")
        else:
            print(f"ERROR: {response.message}")
    print("Channel closed\n")