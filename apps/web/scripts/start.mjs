import { access, cp } from "node:fs/promises";
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const runtime = resolve(root, ".next/standalone/apps/web");
try {
  await access(resolve(runtime, "server.js"));
} catch {
  console.error("No production build found. Run npm run build first.");
  process.exit(1);
}
// Next's standalone output intentionally excludes these generated/public assets.
await cp(resolve(root, ".next/static"), resolve(runtime, ".next/static"), {
  recursive: true,
});
await cp(resolve(root, "public"), resolve(runtime, "public"), {
  recursive: true,
});
const server = spawn(process.execPath, [resolve(runtime, "server.js")], {
  cwd: runtime,
  stdio: "inherit",
  env: {
    ...process.env,
    NODE_ENV: "production",
    HOSTNAME: "127.0.0.1",
    PORT: process.env.PORT || "3100",
  },
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.kill(signal));
}
server.on("error", (error) => {
  console.error(`Could not start BASEERA: ${error.message}`);
  process.exitCode = 1;
});
server.on("exit", (code, signal) => {
  process.exitCode =
    code ?? (signal === "SIGINT" || signal === "SIGTERM" ? 0 : 1);
});
