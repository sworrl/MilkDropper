#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
};

void main() {
    vec2 uv = qt_TexCoord0;
    fragColor = vec4(uv.x, uv.y, 0.5, 1.0) * qt_Opacity;
}
