#!/usr/bin/env python3

import json, sys, wave, struct, random

noise = [random.uniform(-1.0, 1.0) for i in range(1024 * 1024)]

def envelope(attack, decay, sustain, release, length, t):
    v = sustain
    if t < attack:
        v = t / attack
    elif t < attack + decay:
        v = max(2 ** ((t - attack) / decay * -7.2), sustain)

    if t < length:
        return v
    t -= length

    if t < release:
        return v * (2 ** (t / release * -7.2))
    return 0.0

def waveform(form, t, freq, pulse, ctrl):
    if ctrl:
        for ct, cf in ctrl:
            if ct > t:
                break
            freq = cf
        t *= freq
    else:
        t *= freq

    v = 1.0
    if 'tri' in form:
        p = t % 1.0
        v = min(p * 4.0 - 1.0, 3.0 - p * 4.0)
    if 'saw' in form:
        v = ((t + 0.5) % 1.0) * 2.0 - 1.0
    if 'noise' in form:
        v = noise[int(t * 16) % len(noise)]
    if 'pulse' in form:
        p = t % 1.0
        v *= 0.0 if p < pulse else 1.0
    return v

def tone(freq, pulse, form, attack, decay, sustain, release, length, ctrl, t):
    return waveform(form, t, freq, pulse, ctrl) * envelope(attack, decay, sustain, release, length, t)

def play(music, channel, index, t):
    note = None
    found = 0
    for i, e in enumerate(music[index:]):
        if e[1] == channel:
            if e[0] > t:
                break
            note = e
            found = i

    if note is None:
        return 0.0, 0

    return tone(*note[2:], t - note[0]), index + found

def renderMusic(music, outfile):
    f = wave.open(outfile, 'wb')

    f.setparams((1, 2, 48000, 0, 'NONE', 'NONE'))

    index = [0] * 3
    frames = [0] * 48000 * 30 #int(48000 * music[-1][0])
    for i in range(len(frames)):
        t = i / 48000

        v0, index[0] = play(music, 0, index[0], t)
        v1, index[1] = play(music, 1, index[1], t)
        v2, index[2] = play(music, 2, index[2], t)

        v = max(-1.0, min((v0 + v1 + v2) * 0.3, 1.0))
        frames[i] = int(v * 0x7fff)

    f.writeframes(b''.join([struct.pack('<h', fr) for fr in frames]))

if __name__ == '__main__':
    renderMusic(json.load(open(sys.argv[1])), sys.argv[2])
