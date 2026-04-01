import { spawnSync } from 'child_process';
import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';

export interface BackendCapabilities {
  llamaServerFound: boolean;
  llamaServerPath?: string;
  isTurboQuant: boolean;
  turboCacheFlags: string[];
  version?: string;
}

export async function detectCapabilities(vendorDir: string): Promise<BackendCapabilities> {
  const caps: BackendCapabilities = {
    llamaServerFound: false,
    isTurboQuant: false,
    turboCacheFlags: []
  };

  // 1. Look for llama-server in vendor or PATH
  const pathsToTry = [
    path.join(vendorDir, 'llama-cpp-turboquant/build/bin/llama-server'),
    path.join(vendorDir, 'llama.cpp/build/bin/llama-server'),
    'llama-server'
  ];

  for (const p of pathsToTry) {
    const check = spawnSync(p, ['--help'], { encoding: 'utf-8' });
    if (check.status === 0 || (check.stderr && check.stderr.includes('usage:'))) {
      caps.llamaServerFound = true;
      caps.llamaServerPath = p;
      
      const helpText = check.stdout + check.stderr;
      if (helpText.includes('--turbo-cache') || helpText.includes('turbo-quant')) {
        caps.isTurboQuant = true;
      }
      
      // Extract specific turbo flags if any
      const flags = helpText.match(/--turbo-cache-[a-z0-9_]+/g);
      if (flags) {
        caps.turboCacheFlags = Array.from(new Set(flags));
      }
      
      break;
    }
  }

  return caps;
}

export async function runDiagnostics(caps: BackendCapabilities, endpoint?: string) {
  console.log(chalk.blue('\n--- llama.cpp Backend Diagnostics ---'));
  console.log(`${caps.llamaServerFound ? chalk.green('✓') : chalk.red('✗')} llama-server found`);
  if (caps.llamaServerPath) console.log(`  Path: ${caps.llamaServerPath}`);
  
  console.log(`${caps.isTurboQuant ? chalk.green('✓') : chalk.yellow('ℹ')} TurboQuant support detected`);
  if (caps.turboCacheFlags.length > 0) {
    console.log(`  Flags: ${caps.turboCacheFlags.join(', ')}`);
  }

  if (endpoint) {
    const startTime = Date.now();
    try {
      const resp = await fetch(`${endpoint}/health`);
      const duration = Date.now() - startTime;
      console.log(`${resp.ok ? chalk.green('✓') : chalk.red('✗')} Endpoint reachable (${endpoint}) | ${duration}ms`);
    } catch (e) {
      console.log(`${chalk.red('✗')} Endpoint unreachable (${endpoint})`);
    }
  }
}
