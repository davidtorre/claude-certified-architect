// Build lab explainer .docx with embedded diagrams.
const path = require('path');
process.env.NODE_PATH = 'C:\\Users\\david.torre\\AppData\\Roaming\\npm\\node_modules';
require('module').Module._initPaths();

const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, HeadingLevel,
  AlignmentType, LevelFormat, BorderStyle, PageBreak,
} = require('docx');

const HERE = __dirname;
const OUT = path.join(path.dirname(HERE), 'lab04_explained.docx');

const mono = (text) => new TextRun({ text, font: 'Consolas', size: 20 });
const t = (text, opts = {}) => new TextRun({ text, size: 22, ...opts });

const H1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: s })] });
const H2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: s })] });
const P = (children) => new Paragraph({ children: Array.isArray(children) ? children : [children], spacing: { after: 120 } });
const B = (s) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: Array.isArray(s) ? s : [t(s)] });
const CODE = (s) => new Paragraph({
  shading: { type: 'clear', fill: 'F4F4F4' },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: '1A73E8', space: 6 } },
  spacing: { before: 80, after: 120 },
  children: s.split('\n').flatMap((line, i, arr) => {
    const runs = [mono(line)];
    return i < arr.length - 1 ? [...runs, new TextRun({ break: 1 })] : runs;
  }),
});

const img = (file, w, h) => new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new ImageRun({
    type: 'png',
    data: fs.readFileSync(path.join(HERE, file)),
    transformation: { width: w, height: h },
    altText: { title: file, description: file, name: file },
  })],
});

const children = [
  new Paragraph({
    heading: HeadingLevel.TITLE,
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'Lab 04 — Developer Productivity with Claude', bold: true, size: 40 })],
  }),
  P([t('Code walkthrough of ', { italics: true }),
     mono('04_developer_productivity/'),
     t(' — Claude Agent SDK app that explores codebases with tools, MCP, subagents, hooks and a scratchpad.', { italics: true })]),

  H1('1. What this lab builds'),
  P(t('An interactive CLI agent (main.py) that answers questions about a sample Python e-commerce app located in storefront/. The agent is built on top of claude-agent-sdk and combines five orthogonal capabilities:')),
  B('Built-in tools: Read, Write, Edit, Grep, Glob — the primitives for exploring code.'),
  B('MCP server (docs): an in-process tool called lookup_docs that searches mock project documentation in data.py.'),
  B('Explore subagent: a read-only agent with an isolated context, used for multi-file analysis.'),
  B('Hooks: PreToolUse / PostToolUse log every tool call in real time.'),
  B('Scratchpad: scratch.md persists findings across runs so prior exploration is not wasted.'),

  H1('2. Architecture overview'),
  img('arch.png', 540, 324),
  P([t('The main agent sits between the user and three specialised workers: built-in filesystem tools, the '), mono('docs'), t(' MCP server, and the '), mono('explore'), t(' subagent. Hooks wrap every tool call for observability.')]),

  H1('3. Request lifecycle'),
  img('flow.png', 560, 252),
  P(t('Every question flows through run_query() in main.py. The function assembles the system prompt, registers tools/hooks/subagents, then streams the agent reply through rich Markdown.')),

  H1('4. File-by-file walkthrough'),

  H2('main.py — orchestration'),
  B([mono('load_prompt()'), t(' reads prompts/system_prompt.txt and substitutes four placeholders: scratchpad content, scratchpad instructions, MCP-tool guidance, and explore-subagent guidance.')]),
  B([mono('on_pre_tool_use / on_post_tool_use'), t(' are async hook callbacks. They print a coloured one-line summary for each call — spawning a subagent, invoking an MCP tool, or running Grep/Read/etc. They return '), mono('{"continue_": True}'), t(' to let the call proceed.')]),
  B([mono('display_message()'), t(' renders assistant text with rich.Markdown and demotes API-error strings into a '), mono('_last_api_error'), t(' buffer so the CLI shows a friendly message instead of a stack trace.')]),
  B([mono('run_query()'), t(' is the core loop. It builds '), mono('ClaudeAgentOptions'), t(' with model='), mono('claude-sonnet-4-6'), t(', allowed_tools, the '), mono('docs'), t(' MCP server, hooks, '), mono('permission_mode="bypassPermissions"'), t(', '), mono('max_turns=10'), t(' and '), mono('effort="low"'), t(' — then iterates '), mono('query(...)'), t(' and pipes each message into display_message.')]),
  B([t('The interactive '), mono('main()'), t(' prints a menu of six preset questions (find tests, trace validate_email, refactor middleware.py, etc.) and also accepts free-form questions.')]),

  H2('agents.py — Explore subagent'),
  P([t('Exposes '), mono('build_explore_agent()'), t(' which returns a dict '), mono('{"explore": AgentDefinition(...)}'), t('. The '), mono('description'), t(' is what the main model reads to decide when to delegate; the '), mono('prompt'), t(' is loaded from prompts/explore_agent.txt. A TODO in the file asks you to restrict '), mono('tools=["Read", "Grep", "Glob"]'), t(' so the subagent cannot write or spawn sub-subagents.')]),

  H2('tools.py — MCP documentation server'),
  P([t('Defines a single SDK tool with the '), mono('@tool'), t(' decorator: '), mono('lookup_docs(query)'), t('. It scores each entry in '), mono('DOCS'), t(' by how many query words match the concatenated title+section+content, returns the top three as JSON, and is wrapped with '), mono('create_sdk_mcp_server(name="docs", ...)'), t(' in main.py. The tool description is deliberately detailed so the agent chooses it over Grep for documentation-style questions.')]),

  H2('data.py — mock documentation corpus'),
  P(t('A Python list of dicts with five docs: Architecture, API reference, Onboarding, Testing conventions, and Known tech debt. This is what lookup_docs searches.')),

  H2('storefront/ — the codebase under investigation'),
  P([t('A small layered Python app: '), mono('app.py'), t(' (business logic), '), mono('models.py'), t(' (validate_email, format_currency), '), mono('utils.py'), t(' (re-exports from models), '), mono('api/routes.py'), t(' (endpoints), '), mono('api/middleware.py'), t(' (auth + rate-limit). The '), mono('tests/'), t(' directory holds unit tests.')]),

  H2('prompts/'),
  B([mono('system_prompt.txt'), t(' — the main system prompt. Uses four format placeholders and explicitly teaches tool selection and incremental exploration.')]),
  B([mono('explore_agent.txt'), t(' — the subagent system prompt, which defines the investigation-report output format.')]),

  H2('config.py, manage.py, _manage/'),
  P([mono('config.py'), t(' holds ANSI colour codes. '), mono('manage.py'), t(' has two commands: '), mono('restart'), t(' resets files to '), mono('_manage/starter/'), t(' (TODOs intact, scratch.md deleted), and '), mono('solve'), t(' copies '), mono('_manage/solved/'), t(' on top (completed versions).')]),

  H1('5. Lab progression (what the TODOs add)'),
  B('Step 4 — MCP docs server: enhance tool description, build create_sdk_mcp_server, register it in mcp_servers, add mcp__docs__lookup_docs to allowed_tools.'),
  B('Step 5 — Explore subagent: register AgentDefinition, restrict its tools, add Agent to allowed_tools, teach the main prompt when to delegate.'),
  B('Step 6 — Scratchpad: read scratch.md at start of run_query and instruct the agent to append findings after answering.'),
  B('Step 7 — .claude/commands/explore.md: package the whole flow as a reusable slash command with context:fork so it runs in an isolated scratch workspace.'),

  H1('6. Running it'),
  CODE('python -m venv .venv\n.venv\\Scripts\\activate\ncp .env.example .env   # add ANTHROPIC_API_KEY\npip install -r requirements.txt\npython main.py'),
  P([t('Pick a number from the menu or type a free-form question. Scratchpad findings accumulate in '), mono('scratch.md'), t('. Use '), mono('python manage.py restart'), t(' to reset; '), mono('python manage.py solve'), t(' to apply the reference solution.')]),

  H1('7. Rate-limit note'),
  P([t('The default org rate limit for Opus is 30K input tokens/minute, which this lab can exceed on larger queries. '), mono('main.py'), t(' now pins the model to '), mono('claude-sonnet-4-6'), t(' which has its own quota. Swap to '), mono('claude-haiku-4-5-20251001'), t(' for the cheapest/fastest option.')]),

  P({ text: '' }),
  P([t('Tip: to turn this file into a Google Doc, upload it to Google Drive and pick "Open with → Google Docs". All images and headings are preserved.', { italics: true, color: '555555' })]),
];

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, color: '1A365D', font: 'Calibri' },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, color: '1A73E8', font: 'Calibri' },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1 } },
      { id: 'Title', name: 'Title', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 40, bold: true, font: 'Calibri' },
        paragraph: { spacing: { before: 0, after: 240 }, outlineLevel: 0 } },
    ],
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
    }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log('Wrote', OUT);
});
