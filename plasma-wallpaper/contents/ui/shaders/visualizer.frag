#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float iTime;
    float iBass;
    float iMid;
    float iTreble;
    float iEnergy;
    float iBeat;
    vec2 iResolution;
};

// Classic Milkdrop-inspired palette rotation
vec3 palette(float t, float shift) {
    vec3 a = vec3(0.5, 0.5, 0.5);
    vec3 b = vec3(0.5, 0.5, 0.5);
    vec3 c = vec3(1.0, 1.0, 1.0);
    vec3 d = vec3(shift, shift + 0.33, shift + 0.67);
    return a + b * cos(6.28318 * (c * t + d));
}

// Fractal brownian motion noise
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

const mat2 fbmRot = mat2(0.8776, 0.4794, -0.4794, 0.8776); // cos/sin(0.5)

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p = fbmRot * p * 2.0;
        a *= 0.5;
    }
    return v;
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 p = (uv - 0.5) * 2.0;
    p.x *= iResolution.x / iResolution.y;

    float t = iTime * 0.3;
    float bass = iBass;
    float mid = iMid;
    float treble = iTreble;
    float beat = iBeat;

    // Warp the space with audio
    float warp = 1.0 + bass * 0.5;
    p *= warp;

    // Rotating tunnel / spiral
    float angle = atan(p.y, p.x);
    float radius = length(p);

    // Audio-reactive spiral distortion
    float spiral = angle + t * 2.0 + sin(radius * 4.0 - t * 3.0) * (0.3 + bass * 0.7);
    float rings = sin(radius * 8.0 - t * 4.0 + mid * 6.0) * 0.5 + 0.5;

    // FBM warp driven by audio
    vec2 warpUv = p + vec2(
        fbm(p * 2.0 + t + bass * 2.0),
        fbm(p * 2.0 + t * 1.3 + mid * 2.0)
    ) * (0.3 + iEnergy * 0.7);

    float pattern = fbm(warpUv * (2.0 + treble * 3.0) + t);

    // Kaleidoscope effect that intensifies with beat
    float kal = abs(sin(spiral * (3.0 + beat * 4.0))) * rings;

    // Combine layers
    float intensity = pattern * 0.6 + kal * 0.4;
    intensity = pow(intensity, 1.0 - iEnergy * 0.3);

    // Color: palette shifts with time and audio
    float colorShift = t * 0.1 + bass * 0.3;
    vec3 col = palette(intensity + radius * 0.3, colorShift);

    // Add glow on beat
    col += vec3(0.2, 0.1, 0.3) * beat * 2.0;

    // Vignette
    float vig = 1.0 - smoothstep(0.3, 1.5, radius);
    col *= vig;

    // Subtle bloom
    col = pow(col, vec3(0.9 + treble * 0.2));

    fragColor = vec4(col, 1.0) * qt_Opacity;
}
