# Visual Mode Preview Clips

Place short looping MP4 clips here, one per scene `visual_mode`:

```
full_frame.mp4
multi_frame.mp4
continuous.mp4
video.mp4
popup_sequence.mp4
comparison_board.mp4
stat_card.mp4
captions.mp4
```

These are served by Vite at `/visual-modes/{mode}.mp4` and shown in
Settings → Reference → Visual Modes.

## Encoding

~3-5 seconds, looping-friendly cuts, ≤1MB each.

```
ffmpeg -i source.mp4 -t 4 -an -movflags +faststart -crf 28 -preset slow -vcodec libx264 -pix_fmt yuv420p {mode}.mp4
```

## Source

Render one representative scene per mode in Test Lab, then trim with ffmpeg.

The Visual Modes browser gracefully falls back to a placeholder for any
missing file, so partial coverage is fine while the library is being built.
