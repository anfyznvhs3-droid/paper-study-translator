import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import vm from "node:vm";
import ts from "typescript";

const nodeRequire = createRequire(import.meta.url);
const moduleCache = new Map();

export function loadTsModule(absolutePath) {
  const resolved = resolveTsFile(absolutePath);

  const cached = moduleCache.get(resolved);
  if (cached) {
    return cached;
  }

  const source = fs.readFileSync(resolved, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020
    }
  });

  // transpileModule leaves `import.meta` as-is, which is a syntax error
  // outside an ES module under vm.runInNewContext, so redirect it to a
  // shimmed global that mimics Vite's dev-mode `import.meta.env`.
  const runnableOutput = outputText.replace(/import\.meta\.env/g, "globalThis.__importMetaEnv");

  const moduleExports = {};
  moduleCache.set(resolved, moduleExports);

  const context = {
    exports: moduleExports,
    module: { exports: moduleExports },
    require: (request) =>
      request.startsWith(".")
        ? loadTsModule(path.resolve(path.dirname(resolved), request))
        : nodeRequire(request),
    __importMetaEnv: { PROD: false, DEV: true, MODE: "test" }
  };

  vm.runInNewContext(runnableOutput, context);
  return moduleExports;
}

function resolveTsFile(filePath) {
  for (const candidate of [filePath, `${filePath}.ts`, `${filePath}.tsx`]) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate;
    }
  }

  throw new Error(`Cannot resolve TS module: ${filePath}`);
}
