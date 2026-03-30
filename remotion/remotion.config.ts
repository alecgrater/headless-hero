import { Config } from "@remotion/cli/config";
import { enableTailwind } from "@remotion/tailwind-v4";

Config.overrideWebpackConfig((config) => {
  return enableTailwind(config);
});

// Allow reading assets from the data directory
Config.setPublicDir("../data/projects");
