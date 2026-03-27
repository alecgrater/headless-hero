export interface ArtStylePreset {
  name: string;
  prompt: string;
}

export interface ColorPalettePreset {
  name: string;
  colors: string;
}

export interface FontPreset {
  name: string;
  family: string;
}

export const ART_STYLE_PRESETS: ArtStylePreset[] = [
  {
    name: "Flat Illustration",
    prompt:
      "Flat illustration, muted earth tones, thick outlines, dark background",
  },
  {
    name: "Watercolor",
    prompt:
      "Soft watercolor painting, pastel hues, organic textures, white paper background",
  },
  {
    name: "3D Render",
    prompt:
      "Clean 3D render, soft lighting, matte materials, studio background",
  },
  {
    name: "Pixel Art",
    prompt: "Retro pixel art, 16-bit style, vibrant colors, clean edges",
  },
  {
    name: "Cinematic",
    prompt:
      "Cinematic photography, dramatic lighting, shallow depth of field, moody atmosphere",
  },
  {
    name: "Anime",
    prompt:
      "Japanese anime style, bold line art, cel shading, vibrant saturated colors",
  },
  {
    name: "Minimalist",
    prompt:
      "Minimalist vector design, geometric shapes, limited color palette, clean negative space",
  },
  {
    name: "Vintage",
    prompt:
      "Vintage retro poster, grain texture, faded warm colors, halftone dots",
  },
  {
    name: "Neon",
    prompt:
      "Neon-lit cyberpunk, glowing edges, dark background, electric blue and pink tones",
  },
];

export const COLOR_PALETTE_PRESETS: ColorPalettePreset[] = [
  { name: "Midnight", colors: "#1a1a2e, #e94560, #0f3460, #16213e" },
  { name: "Ocean", colors: "#0077b6, #00b4d8, #90e0ef, #caf0f8" },
  { name: "Sunset", colors: "#ff6b35, #f7c59f, #1a535c, #4ecdc4" },
  { name: "Forest", colors: "#2d6a4f, #40916c, #52b788, #d8f3dc" },
  { name: "Lavender", colors: "#7c3aed, #a78bfa, #c4b5fd, #ede9fe" },
  { name: "Ember", colors: "#dc2626, #f97316, #facc15, #fef3c7" },
  { name: "Monochrome", colors: "#f8f9fa, #adb5bd, #495057, #212529" },
  { name: "Coral Reef", colors: "#ff6b6b, #feca57, #48dbfb, #ff9ff3" },
  { name: "Nord", colors: "#2e3440, #88c0d0, #81a1c1, #eceff4" },
];

export const FONT_PRESETS: FontPreset[] = [
  { name: "Montserrat", family: "Montserrat" },
  { name: "DM Sans", family: "DM Sans" },
  { name: "Sora", family: "Sora" },
  { name: "Cabinet Grotesk", family: "Cabinet Grotesk" },
  { name: "Clash Display", family: "Clash Display" },
  { name: "Inter", family: "Inter" },
  { name: "Space Grotesk", family: "Space Grotesk" },
  { name: "Plus Jakarta Sans", family: "Plus Jakarta Sans" },
];
