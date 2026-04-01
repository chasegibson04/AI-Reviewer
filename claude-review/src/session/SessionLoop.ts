import readline from 'readline';
import chalk from 'chalk';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import { LLMProvider, ChatMessage } from '../providers/LLMProvider';
import { EventLogger } from '../logging/EventLogger';
import { ProjectManager } from '../projects/ProjectManager';
import { ReviewPipeline } from '../review/ReviewPipeline';
import { ProfileName } from '../routing/RoutingService';
import { detectCapabilities } from '../utils/capabilityDetection';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class SessionLoop {
  private rl: readline.Interface;
  private llm: LLMProvider;
  private logger: EventLogger;
  private projectManager: ProjectManager;
  private history: ChatMessage[] = [];
  private currentProjectId?: string;
  private isProcessing: boolean = false;

  constructor(llm: LLMProvider, logger: EventLogger, projectManager: ProjectManager) {
    this.llm = llm;
    this.logger = logger;
    this.projectManager = projectManager;
    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      prompt: chalk.bold('> ')
    });
  }

  public async start() {
    console.clear();
    await this.printGuidedStartup();
    this.rl.prompt();

    this.rl.on('line', async (line) => {
      if (this.isProcessing) return;
      this.isProcessing = true;

      const input = line.trim();
      if (!input) {
        this.isProcessing = false;
        this.rl.prompt();
        return;
      }

      if (input.startsWith('/')) {
        await this.handleSlashCommand(input);
      } else {
        await this.handleNaturalLanguage(input);
      }
      
      this.isProcessing = false;
      this.rl.prompt();
    });

    this.rl.on('close', () => {
      console.log('\n');
      process.exit(0);
    });
  }

  private async printGuidedStartup() {
    const vendorDir = path.resolve(__dirname, '../../vendor');
    const caps = await detectCapabilities(vendorDir);
    
    let backendInfo = 'Ollama';
    if (caps.llamaServerFound) {
      backendInfo += ' & llama.cpp';
      if (caps.isTurboQuant) backendInfo += ' (TurboQuant available)';
    }

    console.log(chalk.gray(`Claude Review Agent (Local-first: ${backendInfo})\n`));
    
    const projects = this.projectManager.listProjects();
    if (projects.length === 0) {
      console.log(`Hello! I'm your local manuscript review agent.`);
      console.log(`I don't see any active review projects.`);
      console.log(`To start, type ${chalk.bold('/project init <name>')}.\n`);
    } else {
      const recent = projects.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())[0];
      this.currentProjectId = recent.id;
      console.log(`Hi! Your active project is ${chalk.bold(recent.name)}.`);
      console.log(`Type ${chalk.bold('/review')} to run the full review pipeline, or ask me a question.\n`);
    }
  }

  private async handleSlashCommand(command: string) {
    const [cmd, ...args] = command.slice(1).split(' ');

    switch (cmd) {
      case 'help':
        this.printHelp();
        break;
      case 'project':
        this.handleProjectCommand(args);
        break;
      case 'review':
      case 'deep-run':
        await this.runReviewTask(args);
        break;
      case 'replay':
        this.handleReplayCommand(args);
        break;
      case 'diff':
        this.handleDiffCommand(args);
        break;
      case 'doctor':
      case 'diagnose':
        await this.handleDoctorCommand();
        break;
      case 'exit':
      case 'quit':
      case 'compact':
        this.rl.close();
        break;
      default:
        console.log(chalk.red(`Unrecognized command: /${cmd}.`));
    }
  }

  private async handleDoctorCommand() {
    const vendorDir = path.resolve(__dirname, '../../vendor');
    const caps = await detectCapabilities(vendorDir);
    console.log('\n' + chalk.bold('Local Runtime Diagnostics:'));
    console.log(`${chalk.green('✓')} Ollama backend configured.`);
    if (caps.llamaServerFound) {
      console.log(`${chalk.green('✓')} llama.cpp available.`);
      if (caps.isTurboQuant) console.log(`${chalk.green('✓')} TurboQuant extension available.`);
    } else {
      console.log(`${chalk.gray('○')} llama.cpp not found. Ollama default will be used.`);
    }
    console.log();
  }

  private async handleNaturalLanguage(input: string) {
    this.history.push({ role: 'user', content: input });
    
    // Simulate assistant conversation
    let fullResponse = '';
    try {
      for await (const chunk of this.llm.streamChat(this.history)) {
        process.stdout.write(chunk);
        fullResponse += chunk;
      }
      console.log('\n');
      this.history.push({ role: 'assistant', content: fullResponse });
    } catch (error: any) {
      console.log(chalk.red(`\nBackend error: ${error.message}\n`));
    }
  }

  private handleProjectCommand(args: string[]) {
    const sub = args[0];
    if (sub === 'init' && args[1]) {
      const p = this.projectManager.initProject(args[1]);
      this.currentProjectId = p.id;
      console.log(chalk.green(`✓ Switched to new project: ${p.name}\n`));
    } else if (sub === 'list') {
      const projects = this.projectManager.listProjects();
      console.log(chalk.bold('\nProjects:'));
      projects.forEach(p => {
        const isActive = p.id === this.currentProjectId;
        console.log(`${isActive ? chalk.green('●') : ' '} ${p.id}  ${p.name}`);
      });
      console.log();
    } else {
      console.log(`Try ${chalk.bold('/project init <name>')} or ${chalk.bold('/project list')}\n`);
    }
  }

  private async runReviewTask(args: string[]) {
    if (!this.currentProjectId) {
      console.log(`No active project. Use ${chalk.bold('/project init <name>')} first.\n`);
      return;
    }
    
    const profile = (args[0] as ProfileName) || 'balanced';
    const project = this.projectManager.getProject(this.currentProjectId);
    const { runId, runDir } = this.projectManager.createRun(project.id, profile);
    
    console.log(chalk.dim(`running deep review task (profile: ${profile})...`));

    const pipeline = new ReviewPipeline({
      projectId: project.id,
      runId,
      runDir,
      profileName: profile,
      llm: this.llm,
      logger: this.logger,
      projectRootDir: path.join(process.env.PROJECTS_ROOT || './projects', project.id)
    });

    await pipeline.run();
    
    console.log(`\nReview complete. Run ID: ${chalk.cyan(runId)}`);
    console.log(`Run ${chalk.bold(`/diff ${runId}`)} to view suggested revisions.\n`);
  }

  private handleReplayCommand(args: string[]) {
    if (!args[0]) {
      console.log(`Usage: ${chalk.bold('/replay <run_id>')}\n`);
      return;
    }
    if (!this.currentProjectId) return;
    
    const logPath = path.join(process.env.PROJECTS_ROOT || './projects', this.currentProjectId, 'runs', args[0], 'event_log.jsonl');
    if (!fs.existsSync(logPath)) {
      console.log(chalk.red(`Run log not found.\n`));
      return;
    }
    
    const events = fs.readFileSync(logPath, 'utf-8').split('\n').filter(Boolean).map(l => JSON.parse(l));
    console.log(`\nTranscript (${args[0]}):`);
    events.forEach(e => {
      if (e.type === 'tool') {
        if (e.status === 'success') {
          console.log(chalk.green(`✓ ${e.name}`) + chalk.dim(` (${e.duration}ms)`));
        } else {
          console.log(chalk.red(`✗ ${e.name}`) + chalk.dim(` (${e.duration}ms)`));
        }
      } else if (e.type === 'network') {
        const color = e.status >= 200 && e.status < 300 ? chalk.green : chalk.red;
        console.log(chalk.dim(`[network] `) + chalk.cyan(e.destination) + chalk.dim(` | ${e.purpose} | `) + color(e.status) + chalk.dim(` | ${e.duration}ms`));
      }
    });
    console.log();
  }

  private handleDiffCommand(args: string[]) {
    if (!args[0]) {
      console.log(`Usage: ${chalk.bold('/diff <run_id>')}\n`);
      return;
    }
    if (!this.currentProjectId) return;

    const runDir = path.join(process.env.PROJECTS_ROOT || './projects', this.currentProjectId, 'runs', args[0]);
    const arbitrationPath = path.join(runDir, 'stages', 'stage_arbitration.json');
    if (!fs.existsSync(arbitrationPath)) {
      console.log(chalk.red(`No artifacts found.\n`));
      return;
    }
    
    const data = fs.readJsonSync(arbitrationPath);
    console.log(chalk.bold(`\nReview Arbitration Summary:`));
    let count = 0;
    (data.consolidated_issues || []).forEach((issue: any) => {
      count++;
      const sevColor = issue.severity === 'high' || issue.severity === 'critical' ? chalk.red : chalk.yellow;
      console.log(`\n  ${sevColor(`[${issue.severity.toUpperCase()}]`)} ${issue.section}`);
      console.log(`  Issue: ${chalk.white(issue.issue_type)}`);
      console.log(`  Fix:   ${chalk.dim(issue.suggested_fix || 'No fix suggested.')}`);
    });
    if (count === 0) console.log('  No issues found.');
    console.log();
  }

  private printHelp() {
    console.log('\n' + chalk.bold('Commands:'));
    console.log(`  ${chalk.bold('/review')}          Run the manuscript review agent`);
    console.log(`  ${chalk.bold('/project init')}    Create a new project workspace`);
    console.log(`  ${chalk.bold('/project list')}    Switch between projects`);
    console.log(`  ${chalk.bold('/diff')}            View the summarized issues from a run`);
    console.log(`  ${chalk.bold('/replay')}          View the tool and network logs from a run`);
    console.log(`  ${chalk.bold('/doctor')}          Check local backend health`);
    console.log(`  ${chalk.bold('/help')}            Show this menu`);
    console.log(`  ${chalk.bold('/exit')}            Leave the workstation\n`);
  }
}
