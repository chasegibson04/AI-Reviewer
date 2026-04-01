import { Command } from 'commander';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs-extra';
import chalk from 'chalk';
import { ProjectManager } from './projects/ProjectManager';
import { LLMProvider } from './providers/LLMProvider';
import { LlamaCppProvider } from './providers/LlamaCppProvider';
import { LlamaCppTurboquantProvider } from './providers/LlamaCppTurboquantProvider';
import { EventLogger } from './logging/EventLogger';
import { OllamaProvider } from './providers/OllamaProvider';
import { ReviewPipeline } from './review/ReviewPipeline';
import { ProfileName } from './routing/RoutingService';
import { detectCapabilities, runDiagnostics } from './utils/capabilityDetection';

import { fileURLToPath } from 'url';

import { SessionLoop } from './session/SessionLoop';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const program = new Command();
const projectManager = new ProjectManager(process.env.PROJECTS_ROOT || './projects');
const vendorDir = path.resolve(__dirname, '../vendor');

// Default action: Start interactive session
const startInteractive = async () => {
  const logger = new EventLogger(path.join(process.env.PROJECTS_ROOT || './projects', 'default_run'));
  const llm = new LLMProvider(
    process.env.OPENAI_API_KEY || 'no-key',
    process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
    process.env.OPENAI_MODEL || 'gpt-4o',
    logger
  );
  const session = new SessionLoop(llm, logger, projectManager);
  await session.start();
};

program
  .name('claude-review')
  .description('Advanced terminal-based manuscript review system')
  .version('0.1.0');

program
  .command('doctor')
  .description('Run runtime, provider, and reachability diagnostics')
  .option('--runtime', 'Run deep runtime checks')
  .option('--json', 'Output results in JSON format')
  .action(async (options) => {
    console.log(chalk.blue('\n--- Claude Review Doctor ---'));
    
    const caps = await detectCapabilities(vendorDir);
    const checks = {
      bun: !!process.versions.bun,
      env: fs.existsSync('.env'),
      openai: !!process.env.OPENAI_API_KEY,
      ollama: !!process.env.OLLAMA_BASE_URL,
      llama_cpp: caps.llamaServerFound,
      turbo_quant: caps.isTurboQuant,
      projects_root: fs.existsSync(process.env.PROJECTS_ROOT || './projects')
    };

    if (options.json) {
      console.log(JSON.stringify({ checks, capabilities: caps }, null, 2));
    } else {
      Object.entries(checks).forEach(([key, pass]) => {
        console.log(`${pass ? chalk.green('✓') : chalk.red('✗')} ${key}`);
      });
      if (options.runtime) {
        await runDiagnostics(caps, process.env.LLAMA_CPP_BASE_URL);
      }
    }
  });

program
  .command('project')
  .description('Manage review projects')
  .command('init <name>')
  .action((name) => {
    const project = projectManager.initProject(name);
    console.log(chalk.green(`✓ Project initialized: ${project.name} (${project.id})`));
  });

program
  .command('project-list')
  .action(() => {
    const projects = projectManager.listProjects();
    console.log(chalk.blue('\n--- Projects ---'));
    projects.forEach(p => console.log(`${p.id} | ${p.name}`));
  });

program
  .command('review')
  .description('Perform a manuscript review')
  .option('--project <id>', 'Project ID')
  .option('--profile <name>', 'Review profile', 'balanced')
  .action(async (options) => {
    if (!options.project) {
      console.error(chalk.red('Error: --project <id> is required'));
      process.exit(1);
    }

    try {
      const project = projectManager.getProject(options.project);
      const { runId, runDir } = projectManager.createRun(project.id, options.profile);
      const logger = new EventLogger(runDir);
      
      let llm: LLMProvider;
      
      if (options.profile.startsWith('llama_cpp_turboquant')) {
        llm = new LlamaCppTurboquantProvider(
          process.env.LLAMA_CPP_BASE_URL || 'http://localhost:8080/v1',
          process.env.LLAMA_CPP_MODEL || 'llama-server-turbo',
          logger
        );
        await (llm as LlamaCppTurboquantProvider).verifyTurboSupport();
      } else if (options.profile.startsWith('llama_cpp')) {
        llm = new LlamaCppProvider(
          process.env.LLAMA_CPP_BASE_URL || 'http://localhost:8080/v1',
          process.env.LLAMA_CPP_MODEL || 'llama-server-default',
          logger
        );
      } else if (options.profile === 'openai_remote') {
        llm = new LLMProvider(
          process.env.OPENAI_API_KEY || 'no-key',
          process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
          process.env.OPENAI_MODEL || 'gpt-4o',
          logger
        );
      } else {
        llm = new OllamaProvider(
          process.env.OLLAMA_BASE_URL || 'http://localhost:11434/api',
          process.env.OLLAMA_MODEL || 'qwen2.5-coder:14b',
          logger
        );
      }

      const pipeline = new ReviewPipeline({
        projectId: project.id,
        runId,
        runDir,
        profileName: options.profile as ProfileName,
        llm,
        logger,
        projectRootDir: path.join(process.env.PROJECTS_ROOT || './projects', project.id)
      });

      await pipeline.run();
    } catch (error: any) {
      console.error(chalk.red(`\nReview failed: ${error.message}`));
      process.exit(1);
    }
  });

program
  .command('benchmark')
  .description('Run performance and quality tests on approved targets')
  .option('--target <name>', 'Target project name (miniaturization_d2b, test-existingphactorpaper)')
  .action(async (options) => {
    const targets = {
      'miniaturization_d2b': '20260327051312_miniaturization_d2b',
      'test-existingphactorpaper': '20260325163524_test-existingphactorpaper'
    };

    const targetId = targets[options.target as keyof typeof targets];
    if (!targetId) {
      console.error(chalk.red(`Error: Invalid target. Approved targets: ${Object.keys(targets).join(', ')}`));
      process.exit(1);
    }

    // Safety check for horseshoe crab and pampa
    if (targetId.includes('horseshoe_crabs') || targetId.includes('pampa')) {
      console.error(chalk.red('CRITICAL ERROR: Benchmarking the horseshoe crab or pampa projects is strictly prohibited.'));
      process.exit(1);
    }

    console.log(chalk.blue(`\n--- Benchmarking Target: ${options.target} (${targetId}) ---`));

    try {
      const project = projectManager.initProject(`benchmark_${options.target}`);
      const { runId, runDir } = projectManager.createRun(project.id, 'balanced');
      const logger = new EventLogger(runDir);
      
      const llm = new OllamaProvider(
        process.env.OLLAMA_BASE_URL || 'http://localhost:11434/api',
        process.env.OLLAMA_MODEL || 'mistral-small3.2:latest',
        logger
      );

      const pipeline = new ReviewPipeline({
        projectId: project.id,
        runId,
        runDir,
        profileName: 'balanced',
        llm,
        logger,
        projectRootDir: path.join(process.env.PROJECTS_ROOT || './projects', project.id)
      });

      const startTime = Date.now();
      await pipeline.run();
      const duration = Date.now() - startTime;

      const report = {
        target: options.target,
        targetId,
        runId,
        duration,
        timestamp: new Date().toISOString(),
        toolEvents: logger.getToolEvents(),
        networkEvents: logger.getNetworkEvents()
      };

      const reportPath = path.join('reports', `benchmark_${options.target}_${Date.now()}.json`);
      fs.ensureDirSync('reports');
      fs.writeJsonSync(reportPath, report, { spaces: 2 });
      
      console.log(chalk.green(`\n✓ Benchmark complete. Report written to ${reportPath}`));
      console.log(`Total Duration: ${duration}ms`);
    } catch (error: any) {
      console.error(chalk.red(`\nBenchmark failed: ${error.message}`));
      process.exit(1);
    }
  });

program
  .command('interactive')
  .description('Start interactive review workstation')
  .action(startInteractive);

program.action(() => {
  if (program.args.length === 0) {
    startInteractive();
  } else {
    program.help();
  }
});

program.parse(process.argv);
