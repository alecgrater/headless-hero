import { Config } from "@remotion/cli/config";
import { enableTailwind } from "@remotion/tailwind-v4";

Config.overrideWebpackConfig((config) => {
  return enableTailwind(config);
});

// Force keyframe every 2 seconds (60 frames at 30fps).
// Without this, long compositions produce corrupt H.264 with insufficient
// keyframes, making the video unplayable past the first GOP.
Config.overrideFfmpegCommand(({ args, type }) => {
  if (type === "pre-stitcher") {
    const yIdx = args.indexOf("-y");
    if (yIdx >= 0) {
      return [...args.slice(0, yIdx), "-g", "60", ...args.slice(yIdx)];
    }
  }
  return args;
});
