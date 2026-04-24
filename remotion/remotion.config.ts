import { Config } from "@remotion/cli/config";
import { enableTailwind } from "@remotion/tailwind-v4";

Config.overrideWebpackConfig((config) => {
  return enableTailwind(config);
});

// Force keyframe every 2 seconds (60 frames at 30fps).
// Applied to BOTH pre-stitcher and stitcher steps because Remotion may skip
// the pre-stitcher when memory is tight (common for long compositions).
// Without this, long H.264 exports have too few keyframes and appear frozen.
Config.overrideFfmpegCommand(({ args, type }) => {
  console.error(`[HH-FFmpeg] override called: type=${type}, args=${args.length}`);
  const yIdx = args.indexOf("-y");
  if (yIdx >= 0) {
    console.error(`[HH-FFmpeg] injecting -g 60 for ${type} step`);
    return [...args.slice(0, yIdx), "-g", "60", ...args.slice(yIdx)];
  }
  return args;
});
