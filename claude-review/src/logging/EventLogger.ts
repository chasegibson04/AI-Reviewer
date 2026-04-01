import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';

export interface ToolEvent {
  name: string;
  purpose: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'pending' | 'success' | 'failure';
  error?: string;
  artifacts?: string[];
}

export interface NetworkEvent {
  destination: string;
  purpose: string;
  status: number;
  duration: number;
  timestamp: number;
  model?: string;
}

export class EventLogger {
  private toolEvents: ToolEvent[] = [];
  private networkEvents: NetworkEvent[] = [];
  private logFilePath: string;

  constructor(runDir: string) {
    this.logFilePath = path.join(runDir, 'event_log.jsonl');
    fs.ensureFileSync(this.logFilePath);
  }

  public logToolStart(name: string, purpose: string): ToolEvent {
    const event: ToolEvent = {
      name,
      purpose,
      startTime: Date.now(),
      status: 'pending'
    };
    this.toolEvents.push(event);
    
    // Claude Code style tool invocation
    console.log(chalk.dim(`\n> ${name}`));
    console.log(chalk.dim(`  purpose: "${purpose}"`));
    
    return event;
  }

  public logToolEnd(event: ToolEvent, status: 'success' | 'failure', error?: string, artifacts?: string[]) {
    event.endTime = Date.now();
    event.duration = event.endTime - event.startTime;
    event.status = status;
    event.error = error;
    event.artifacts = artifacts;

    if (status === 'success') {
      console.log(chalk.green(`✓ ${event.name}`) + chalk.dim(` (${event.duration}ms)`));
    } else {
      console.log(chalk.red(`✗ ${event.name}`) + chalk.dim(` (${event.duration}ms)`));
      console.log(chalk.red(`  Error: ${error}`));
    }

    this.persistEvent({ type: 'tool', ...event });
  }

  public logNetwork(networkEvent: NetworkEvent) {
    this.networkEvents.push(networkEvent);
    
    // Explicit network visibility as requested, but cleaner
    const statusColor = networkEvent.status >= 200 && networkEvent.status < 300 ? chalk.green : chalk.red;
    console.log(
      chalk.dim(`[network] `) + chalk.cyan(networkEvent.destination) + chalk.dim(` | ${networkEvent.purpose} | `) + statusColor(networkEvent.status) + chalk.dim(` | ${networkEvent.duration}ms`)
    );
    
    this.persistEvent({ type: 'network', ...networkEvent });
  }

  private persistEvent(event: any) {
    fs.appendFileSync(this.logFilePath, JSON.stringify(event) + '\n');
  }

  public getToolEvents() { return this.toolEvents; }
  public getNetworkEvents() { return this.networkEvents; }
}

