import React from 'react';
import type { LocalJSXCommandCall } from '../../types/command.js';
import { Box, Text, Newline } from '../../ink.js';
import { PressEnterToContinue } from '../../components/PressEnterToContinue.js';
import { useAppState } from '../../state/AppState.js';

export const call: LocalJSXCommandCall = (onDone, _context, _args) => {
  return Promise.resolve(<ArtifactsList onDone={onDone} />);
};

function ArtifactsList({ onDone }: { onDone: () => void }) {
  // In a real implementation, we would list files from the output directory
  // For now, we'll guide the user to where they are typically stored
  return (
    <Box flexDirection="column" padding={1}>
      <Text bold color="green">Review Artifacts</Text>
      <Newline />
      <Text>Artifacts are stored in the <Text color="cyan">outputs/</Text> directory of your project.</Text>
      <Newline />
      <Text bold>Key files to look for:</Text>
      <Text>- <Text color="yellow">run_summary.json</Text>: Overview of the review run.</Text>
      <Text>- <Text color="yellow">manuscript_comment_manifest.json</Text>: All identified issues and suggestions.</Text>
      <Text>- <Text color="yellow">session_transcript.md</Text>: Full record of the review session.</Text>
      <Newline />
      <Text dimColor>Tip: Use the `render_outputs` tool to regenerate these if needed.</Text>
      <Newline />
      <PressEnterToContinue />
    </Box>
  );
}
