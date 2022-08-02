#version 430
layout(local_size_x = 16) in;

uniform uint sampleOffset;
uniform float sampleFrequency;
uniform int noteCount;

struct Note
{
    float timestamp;
    float frequency;
    int waveform;
    float attack;
    float decay;
    float sustain;
    float release;
    float duration;
};

layout(std430, binding = 0) restrict readonly buffer musicBuffer
{
    Note notes[];
};

layout(binding = 1) uniform samplerBuffer noiseBuffer;

layout(r16i, binding = 0) uniform writeonly iimageBuffer sampleBuffer;

float envelope(float attack, float decay, float sustain, float release, float duration, float t)
{
    float v = sustain;
    if(t < attack)
        v = clamp(t / attack, 0.0f, 1.0f);
    else if(t < attack + decay)
        v = max(exp2((t - attack) / decay * -7.2f), sustain);

    if(t < duration)
        return v;
    t -= duration;

    if(t < release)
        return v * exp2(t / release * -7.2f);
    return 0.0f;
}

float waveform(int form, float t, float freq, float pulse/*, ctrl*/)
{
    /*if ctrl:
        for ct, cf in ctrl:
            if ct > t:
                break
            freq = cf
        t *= freq
    else:*/
        t *= freq;

    float v = 1.0f;
    if((form & 0x10) != 0) // tri
    {
        float p = fract(t);
        v = min(p * 4.0f - 1.0f, 3.0f - p * 4.0f);
    }
    if((form & 0x20) != 0) // saw
        v = fract(t + 0.5f) * 2.0f - 1.0f;
    if((form & 0x40) != 0) // noise
        v = texelFetch(noiseBuffer, int(t * 16.0f) & (1024 * 1024 - 1)).x * 2.0f - 1.0f;
    if((form & 0x80) != 0) // pulse
        v *= float(fract(t) > pulse);

    return v;
}

float playNote(Note n, float t)
{
    t -= n.timestamp;

    float v = waveform(n.waveform, t, n.frequency, /*n.pulse*/0.0f);
    v *= envelope(n.attack, n.decay, n.sustain, n.release, n.duration, t);
    return v;
}

void main()
{
    float t = float(sampleOffset + gl_GlobalInvocationID.x) / sampleFrequency;

    int found[3] = {0, 0, 0};
    for(int i = 1; i < noteCount; i++)
    {
        if(notes[i].timestamp > t)
            break;

        found[notes[i].waveform & 0xf] = i;
    }

    float v = playNote(notes[found[0]], t);
    v += playNote(notes[found[1]], t);
    v += playNote(notes[found[2]], t);

    int s = int(clamp(v * 0.3f, -1.0f, 1.0f) * 32767.0f);
    imageStore(sampleBuffer, int(gl_GlobalInvocationID.x), ivec4(s, 0, 0, 0));
}
