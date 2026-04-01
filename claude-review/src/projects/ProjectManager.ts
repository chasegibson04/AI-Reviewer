import fs from 'fs-extra';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';

export interface ProjectMetadata {
  id: string;
  name: string;
  sourceFile?: string;
  createdAt: string;
  updatedAt: string;
}

export interface RunMetadata {
  id: string;
  timestamp: string;
  profile: string;
  status: 'running' | 'success' | 'failure';
}

export class ProjectManager {
  private rootDir: string;

  constructor(rootDir: string) {
    this.rootDir = path.resolve(rootDir);
    fs.ensureDirSync(this.rootDir);
  }

  public initProject(name: string): ProjectMetadata {
    const id = uuidv4();
    const projectDir = path.join(this.rootDir, id);
    fs.ensureDirSync(projectDir);
    fs.ensureDirSync(path.join(projectDir, 'source'));
    fs.ensureDirSync(path.join(projectDir, 'runs'));
    fs.ensureDirSync(path.join(projectDir, 'cache'));

    const metadata: ProjectMetadata = {
      id,
      name,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    fs.writeJsonSync(path.join(projectDir, 'metadata.json'), metadata, { spaces: 2 });
    return metadata;
  }

  public getProject(id: string): ProjectMetadata {
    const projectDir = path.join(this.rootDir, id);
    if (!fs.existsSync(projectDir)) {
      throw new Error(`Project ${id} not found`);
    }
    return fs.readJsonSync(path.join(projectDir, 'metadata.json'));
  }

  public listProjects(): ProjectMetadata[] {
    const dirs = fs.readdirSync(this.rootDir);
    const projects: ProjectMetadata[] = [];
    for (const dir of dirs) {
      const metaPath = path.join(this.rootDir, dir, 'metadata.json');
      if (fs.existsSync(metaPath)) {
        projects.push(fs.readJsonSync(metaPath));
      }
    }
    return projects;
  }

  public createRun(projectId: string, profile: string): { runId: string, runDir: string } {
    const timestamp = format(new Date(), 'yyyyMMdd_HHmmss');
    const runId = `${timestamp}_${uuidv4().slice(0, 8)}`;
    const runDir = path.join(this.rootDir, projectId, 'runs', runId);
    fs.ensureDirSync(runDir);
    fs.ensureDirSync(path.join(runDir, 'stages'));

    const meta: RunMetadata = {
      id: runId,
      timestamp: new Date().toISOString(),
      profile,
      status: 'running',
    };
    fs.writeJsonSync(path.join(runDir, 'run_summary.json'), meta, { spaces: 2 });

    return { runId, runDir };
  }

  public getRunDir(projectId: string, runId: string): string {
    return path.join(this.rootDir, projectId, 'runs', runId);
  }
}

// Utility to match the format function from date-fns if not available or just use native
function format(date: Date, fmt: string): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return fmt
    .replace('yyyy', date.getFullYear().toString())
    .replace('MM', pad(date.getMonth() + 1))
    .replace('dd', pad(date.getDate()))
    .replace('HH', pad(date.getHours()))
    .replace('mm', pad(date.getMinutes()))
    .replace('ss', pad(date.getSeconds()));
}
