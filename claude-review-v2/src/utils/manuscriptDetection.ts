import { getFsImplementation } from './fsOperations.js';
import { join } from 'path';
import { getCwd } from './cwd.js';

export type ManuscriptFile = {
  path: string;
  type: 'docx' | 'pdf';
};

export type ProjectSnapshot = {
  projectId: string;
  manuscriptCount: number;
  artifactCount: number;
};

const BLOCKED_PROJECT_SNIPPETS = ['pampa', 'horseshoe'];

function isBlockedProjectName(name: string): boolean {
  const lowered = name.toLowerCase();
  return BLOCKED_PROJECT_SNIPPETS.some(snippet => lowered.includes(snippet));
}

export async function detectManuscripts(dir: string = getCwd()): Promise<ManuscriptFile[]> {
  const fs = getFsImplementation();
  const manuscripts: ManuscriptFile[] = [];

  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile()) {
        const name = entry.name.toLowerCase();
        if (name.endsWith('.docx')) {
          manuscripts.push({ path: join(dir, entry.name), type: 'docx' });
        } else if (name.endsWith('.pdf')) {
          manuscripts.push({ path: join(dir, entry.name), type: 'pdf' });
        }
      } else if (entry.isDirectory() && entry.name === 'projects') {
        const projectRoot = join(dir, entry.name);
        const projectEntries = await fs.readdir(projectRoot, { withFileTypes: true });
        for (const projectEntry of projectEntries) {
          if (!projectEntry.isDirectory()) continue;
          if (isBlockedProjectName(projectEntry.name)) continue;
          const subManuscripts = await detectManuscripts(join(projectRoot, projectEntry.name));
          manuscripts.push(...subManuscripts);
        }
      }
    }
  } catch (error) {
    // Ignore errors
  }

  return manuscripts;
}

export async function isOllamaRunning(): Promise<boolean> {
  try {
    const response = await fetch('http://localhost:11434/api/tags', {
      signal: AbortSignal.timeout(2000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function detectProjectSnapshots(dir: string = getCwd()): Promise<ProjectSnapshot[]> {
  const fs = getFsImplementation();
  const snapshots: ProjectSnapshot[] = [];
  const projectsDir = join(dir, 'projects');

  try {
    const projectEntries = await fs.readdir(projectsDir, { withFileTypes: true });
    for (const projectEntry of projectEntries) {
      if (!projectEntry.isDirectory()) continue;
      if (isBlockedProjectName(projectEntry.name)) continue;

      const projectPath = join(projectsDir, projectEntry.name);
      const manuscriptDir = join(projectPath, 'materials', 'manuscript');
      const runsDir = join(projectPath, 'runs');

      let manuscriptCount = 0;
      let artifactCount = 0;

      try {
        const manuscripts = await fs.readdir(manuscriptDir, { withFileTypes: true });
        manuscriptCount = manuscripts.filter(
          item =>
            item.isFile() &&
            (item.name.toLowerCase().endsWith('.docx') || item.name.toLowerCase().endsWith('.pdf')),
        ).length;
      } catch {
        manuscriptCount = 0;
      }

      try {
        const runs = await fs.readdir(runsDir, { withFileTypes: true });
        artifactCount = runs.filter(item => item.isDirectory()).length;
      } catch {
        artifactCount = 0;
      }

      snapshots.push({
        projectId: projectEntry.name,
        manuscriptCount,
        artifactCount,
      });
    }
  } catch {
    // Ignore when projects folder is absent.
  }

  return snapshots;
}

export async function getEnvironmentSummary(cwd: string): Promise<string> {
  const [manuscripts, ollamaOk, projects] = await Promise.all([
    detectManuscripts(cwd),
    isOllamaRunning(),
    detectProjectSnapshots(cwd),
  ]);

  let summary = "## Manuscript Review Environment Status\n";
  summary += `Ollama Status: ${ollamaOk ? "Connected and Running" : "OFFLINE (Local models will not work)"}\n`;

  if (manuscripts.length > 0) {
    summary += `Manuscripts Found:\n${manuscripts.map(m => `- ${m.path}`).join("\n")}\n`;
  } else {
    summary += "Manuscripts Found: None detected. You should ask the user to provide a path to a manuscript file or add one to the current directory.\n";
  }

  if (projects.length > 0) {
    summary += `Projects Found: ${projects.length}\n`;
    for (const project of projects.slice(0, 8)) {
      summary += `- ${project.projectId}: manuscripts=${project.manuscriptCount}, runs=${project.artifactCount}\n`;
    }
  } else {
    summary += "Projects Found: None in ./projects\n";
  }

  summary += `Blocked project policy: ${BLOCKED_PROJECT_SNIPPETS.join(', ')}\n`;
  return summary;
}
