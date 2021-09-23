#!/usr/bin/env python3

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
    width, height = 640, 480 #3840, 2160
    SDL_Init(SDL_INIT_VIDEO)

    window = SDL_CreateWindow(b"shadergon",
                              SDL_WINDOWPOS_UNDEFINED,
                              SDL_WINDOWPOS_UNDEFINED, width, height,
                              SDL_WINDOW_OPENGL)

    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 4)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_PROFILE_MASK,
                              video.SDL_GL_CONTEXT_PROFILE_CORE)
    context = SDL_GL_CreateContext(window)

    gameData = '''
layout(std430, binding = 0) restrict buffer gameBuffer
{
    bool inited;
    bool playing;
    uint lastTicks;
    vec4 ColorA;
    vec4 ColorB;

    vec2 angleOffset;
    vec3 pointParams; // x y size
    vec4 ring0Params; // radius with type(0 2 3 -5) rotation
    vec4 ring1Params; // radius with type(0 2 3 -5) rotation
};'''

    programLogic = compile_program(compute_source = '''#version 430
layout(local_size_x = 1) in;

uniform uint ticks;
uniform vec2 controls;

%s

const float[] modes = {2, 3, -5};

void main()
{
    if(!inited)
    {
        playing = false;
        angleOffset = vec2(1, 0);
        lastTicks = ticks;
        inited = true;
    }
    
    float deltaTime = float(ticks - lastTicks) / 1000.0;
    lastTicks = ticks;

    float angle = radians(30) * deltaTime;
    angleOffset *= mat2(cos(angle), sin(angle), -sin(angle), cos(angle));

    if(playing)
    {
        ring0Params.x -= 100.0 * deltaTime;
        if(ring0Params.x + 25 <= 60)
        {
            ring0Params.x = 600;
            ring0Params.z = modes[ticks %% 3];
            ring0Params.w = float((ticks >> 1) %% 6);
        }

        ring1Params.x -= 100.0 * deltaTime;
        if(ring1Params.x + 25 <= 60)
        {
            ring1Params.x = 600;
            ring1Params.z = modes[ticks %% 3];
            ring1Params.w = float((ticks >> 1) %% 6);
        }

        angle = radians(200) * controls.x * deltaTime;
        pointParams.xy *= mat2(cos(angle), sin(angle), -sin(angle), cos(angle));
    }
    else
    {
        if(controls.y != 0)
        {
            ColorA = vec4(0.0,0.0,1.0,1.0);
            ColorB = vec4(0.0,1.0,0.0,1.0);

            pointParams = vec3(100, 0, 10); 
            ring0Params = vec4(200, 30, 3, 0); 
            ring1Params = vec4(500, 30, -5, 1);
            playing = true;
        }
        else
        {
            ColorA = vec4(0.2,0.2,0.2,1.0);
            ColorB = vec4(0.5,0.5,0.5,1.0);

            pointParams = vec3(0); 
            ring0Params = vec4(0); 
            ring1Params = vec4(0);
        }
    }
}
''' % gameData)

    programBlit = compile_program(vertex_source = '''#version 330

out vec2 pos;

void main()
{
    vec2 p = vec2(gl_VertexID & 1, gl_VertexID >> 1);

    pos = p * 2.0;
    gl_Position = vec4(p * 4.0 - 1.0, 0.0, 1.0);
}
''', fragment_source = '''#version 430

uniform vec2 center;

%s

layout(location = 0) out vec4 result;

const vec2[3] faces = vec2[3](vec2(1, 0), vec2(cos(radians(60)), sin(radians(60))), vec2(cos(radians(120)), sin(radians(120))));

bool innerHexagon(vec2 v, out vec4 c)
{
    c = vec4(1);

    for(int i = 0; i < 3; i++)
        if(abs(dot(faces[i], v)) > 60)
            return false;

    for(int i = 0; i < 3; i++)
        if(abs(dot(faces[i], v)) > 50)
            return true;

    c = ColorA;
    return true;
}

bool hexagon(vec2 v, float angle,
             float radius, float width,
             float type, float offset) // type = [0 2 3 -5]
{
    for(int i = 0; i < 3; i++)
        if(abs(dot(faces[i], v)) > radius + width)
            return false;

    for(int i = 0; i < 3; i++)
        if(abs(dot(faces[i], v)) > radius)
        {
            float ccc = angle / radians(360) + offset / 6 + 0.5 / 6;
            return fract(ccc * max(type, 1)) < abs(type / 6.0);
        }

    return false;
}

bool point(vec2 v, vec2 p, float size)
{
    vec2 d = abs(v - p);
    return dot(d, d) < size * size; //max(d.x, d.y) < size;
}

vec4 effect(vec2 pixel_coords)
{
    vec2 v = pixel_coords - center;
    v *= mat2(angleOffset.x, -angleOffset.y,
              angleOffset.y, angleOffset.x);

    vec4 c;
    if(innerHexagon(v, c))
        return c;

    bool player = point(v, pointParams.xy, pointParams.z);

    float angle = atan(v.y, v.x);

    bool barrier = hexagon(v, angle, ring0Params.x, ring0Params.y, ring0Params.z, ring0Params.w)
                || hexagon(v, angle, ring1Params.x, ring1Params.y, ring1Params.z, ring1Params.w);

    if(player && barrier)
        playing = false;

    if(player || barrier)
        return vec4(1);

    float sector = fract(angle / radians(120) - 0.25);
    return mix(ColorA, ColorB, float(sector > 0.5));
}

void main()
{
    result = effect(gl_FragCoord.xy);
}
''' % gameData)

    gameBuffer = glGenBuffers(1)
    glBindBuffer(GL_SHADER_STORAGE_BUFFER, gameBuffer);
    glBufferStorage(GL_SHADER_STORAGE_BUFFER, 7 * 16, 7 * 16 * b'\00', 0)
    glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, gameBuffer)

    vao = glGenVertexArrays(1)
    glBindVertexArray(vao)

    #clock = pygame.time.Clock() 

    controls = 0
    fire = 0
    quit = False
    while not quit:
        e = SDL_Event()
        while SDL_PollEvent(ctypes.byref(e)) != 0:
            if e.type == SDL_QUIT:
                quit = True
            elif e.type in (SDL_KEYDOWN, SDL_KEYUP) and not e.key.repeat:
                if e.key.keysym.sym == SDLK_LEFT:
                    controls += -1 if e.type == SDL_KEYDOWN else 1
                elif e.key.keysym.sym == SDLK_RIGHT:
                    controls += 1 if e.type == SDL_KEYDOWN else -1
                elif e.key.keysym.sym == SDLK_SPACE:
                    fire = e.type == SDL_KEYDOWN
                elif e.key.keysym.sym == SDLK_ESCAPE:
                    quit = True

        glUseProgram(programLogic)
        glUniform1ui(glGetUniformLocation(programLogic, 'ticks'), SDL_GetTicks())
        glUniform2f(glGetUniformLocation(programLogic, 'controls'), controls, fire)
        glDispatchCompute(1, 1, 1);

        glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)

        glUseProgram(programBlit)
        glUniform2f(glGetUniformLocation(programBlit, 'center'), width / 2, height / 2)
        glDrawArrays(GL_TRIANGLES, 0, 3)
        
        glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)

        SDL_Delay(16)
        SDL_GL_SwapWindow(window)
