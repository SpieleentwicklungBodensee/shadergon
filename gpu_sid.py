#!/usr/bin/env python3

import random, struct, json, sys, wave
from sdl2 import *
from OpenGL.GL import *

def add_shader(program, shader_type, source):
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)

    status = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not status:
        print(glGetShaderInfoLog(shader))
        return False

    glAttachShader(program, shader)
    glDeleteShader(shader)
    return True

def compile_program(vertex_source = None, fragment_source = None, compute_source = None):
    program = glCreateProgram()

    if vertex_source:
        add_shader(program, GL_VERTEX_SHADER, vertex_source)
    if fragment_source:
        add_shader(program, GL_FRAGMENT_SHADER, fragment_source)
    if compute_source:
        add_shader(program, GL_COMPUTE_SHADER, compute_source)

    glLinkProgram(program)
    return program

if __name__ == '__main__':
    sampleFrequency = 48000
    sampleSize = 4096

    width, height = 640, 480 #3840, 2160
    SDL_Init(SDL_INIT_VIDEO)

    window = SDL_CreateWindow(b"gpu_sid",
                              SDL_WINDOWPOS_UNDEFINED,
                              SDL_WINDOWPOS_UNDEFINED, width, height,
                              SDL_WINDOW_OPENGL)

    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 4)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_PROFILE_MASK,
                              video.SDL_GL_CONTEXT_PROFILE_CORE)
    context = SDL_GL_CreateContext(window)

    synthesizer = compile_program(compute_source = open('sid.glsl').read())

    noiseData = b''.join([struct.pack('H', random.randrange(0, 0xffff)) for i in range(1024 * 1024)])

    noiseMap = glGenTextures(1)
    glActiveTexture(GL_TEXTURE1)
    glBindTexture(GL_TEXTURE_BUFFER, noiseMap)

    noiseBuffer = glGenBuffers(1)
    glBindBuffer(GL_TEXTURE_BUFFER, noiseBuffer);
    glBufferStorage(GL_TEXTURE_BUFFER, len(noiseData), noiseData, 0)
    glTexBuffer(GL_TEXTURE_BUFFER, GL_R16, noiseBuffer)
    glActiveTexture(GL_TEXTURE0)

    music = json.load(open(sys.argv[1]))

    musicData = [struct.pack('ffifffff', float('inf'), 0.0, 0, 1.0, 1.0, 1.0, 1.0, 0.0)]
    for n in music:
        waveform = n[1]
        if 'tri' in n[4]:
            waveform |= 0x10
        if 'saw' in n[4]:
            waveform |= 0x20
        if 'noise' in n[4]:
            waveform |= 0x40
        if 'pulse' in n[4]:
            waveform |= 0x80

        musicData.append(struct.pack('ffifffff', n[0], n[2], waveform, n[5], n[6], n[7], n[8], n[9]))

    noteCount = len(musicData)
    musicData = b''.join(musicData)

    musicBuffer = glGenBuffers(1)
    glBindBuffer(GL_SHADER_STORAGE_BUFFER, musicBuffer)
    glBufferData(GL_SHADER_STORAGE_BUFFER, len(musicData), musicData, GL_STATIC_DRAW)
    glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, musicBuffer)

    sampleBuffer = glGenBuffers(1)
    glBindBuffer(GL_COPY_READ_BUFFER, sampleBuffer)
    glBufferStorage(GL_COPY_READ_BUFFER, sampleSize * 2, None, GL_CLIENT_STORAGE_BIT)

    sampleMap = glGenTextures(1)
    glBindTexture(GL_TEXTURE_BUFFER, sampleMap)
    glTexBuffer(GL_TEXTURE_BUFFER, GL_R16I, sampleBuffer)
    glBindImageTexture(0, sampleMap, 0, GL_TRUE, 0, GL_READ_WRITE, GL_R16I)

    glUseProgram(synthesizer)
    glUniform1f(glGetUniformLocation(synthesizer, 'sampleFrequency'), sampleFrequency)
    glUniform1i(glGetUniformLocation(synthesizer, 'noteCount'), noteCount)

    data = []
    for i in range((sampleFrequency * 200) // sampleSize):
        glUniform1ui(glGetUniformLocation(synthesizer, 'sampleOffset'), i * sampleSize)
        glDispatchCompute(sampleSize // 16, 1, 1)
        glFinish()

        data.append(glGetBufferSubData(GL_COPY_READ_BUFFER, 0, sampleSize * 2))

    data = b''.join(data)
    f = wave.open(sys.argv[2], 'wb')
    f.setparams((1, 2, sampleFrequency, 0, 'NONE', 'NONE'))
    f.writeframes(data)

