/**
 * Keyword matching between a job posting and a resume, the way an applicant
 * tracking system (ATS) reads them.
 *
 * `pinloop ats` scores each posting by how many of the skills its text names
 * also appear in the person's resume, and lists the ones that do and the ones
 * that do not, with how often each side says them. It makes no model call and
 * contacts no server of its own: it works on posting text `pinloop fetch` already
 * handed back and on the words read out of the stored resume. That makes it free
 * to run over every posting this account holds, and a cheap first sieve before
 * `pinloop judge` spends a real judgment.
 *
 * Skills come from two places. A fixed lexicon below names the skills, tools and
 * practices postings ask for by name, each with the spellings it goes by, so
 * "test automation" and "automated testing" are one skill rather than two. On
 * top of that, tool names the lexicon does not know are picked up from the
 * posting itself: an acronym written in capitals, like SDLC, or a name written
 * with a capital in the middle, like TestRail, is very likely a tool or a
 * standard, and a resume that never says it is missing it.
 *
 * The score is out of 100. Every skill the posting names carries a weight: one,
 * plus a little for each time the posting repeats it, plus one more when it sits
 * in the job title, because a title says what the job is. The score is the
 * weight of the skills the resume carries over the weight of all of them.
 */

export type SkillKind = 'hard' | 'soft' | 'tool';

/** One skill the posting names, with how often each side says it. */
export type SkillHit = {
  keyword: string;
  kind: SkillKind;
  /** how many times the posting's text says it */
  posting: number;
  /** how many times the resume says it */
  resume: number;
  /** whether the job title itself says it */
  in_title: boolean;
  /** the spelling the posting itself uses, as written there */
  posting_spelling: string;
};

export type AtsReport = {
  /** 0 to 100 */
  score: number;
  matched: SkillHit[];
  missing: SkillHit[];
};

type LexiconEntry = { name: string; kind: SkillKind; aliases: string[] };

const L = (name: string, kind: SkillKind, ...aliases: string[]): LexiconEntry => ({
  name,
  kind,
  aliases: [name, ...aliases],
});

/**
 * The skills postings ask for by name. Weighted toward software testing, because
 * that is where this began, but broad enough to read an ordinary software
 * posting. Aliases are matched as whole words, case-insensitively, with a
 * trailing s, es, ed or ing allowed, and spaces in an alias also match a hyphen
 * or a slash.
 */
const LEXICON: readonly LexiconEntry[] = [
  // Testing practice
  L('QA', 'hard', 'quality assurance', 'quality engineering', 'software quality'),
  L('manual testing', 'hard', 'manual test', 'manual qa', 'manual tester'),
  L('test automation', 'hard', 'automated testing', 'automation testing', 'test automation framework', 'automation'),
  L('regression testing', 'hard', 'regression test', 'regression suite', 'regression'),
  L('exploratory testing', 'hard', 'exploratory test'),
  L('functional testing', 'hard', 'functional test'),
  L('integration testing', 'hard', 'integration test'),
  L('end-to-end testing', 'hard', 'end to end testing', 'e2e testing', 'e2e test', 'e2e'),
  L('unit testing', 'hard', 'unit test'),
  L('acceptance testing', 'hard', 'uat', 'user acceptance testing'),
  L('smoke testing', 'hard', 'smoke test'),
  L('performance testing', 'hard', 'performance test', 'load testing', 'load test', 'stress testing'),
  L('accessibility testing', 'hard', 'accessibility', 'a11y', 'wcag'),
  L('security testing', 'hard', 'penetration testing', 'pen testing', 'pentest'),
  L('usability testing', 'hard', 'usability'),
  L('API testing', 'hard', 'api test', 'rest api testing'),
  L('mobile testing', 'hard', 'mobile test', 'mobile qa', 'mobile app testing'),
  L('cross-browser testing', 'hard', 'cross browser', 'browser compatibility'),
  L('test cases', 'hard', 'test case', 'test case design'),
  L('test plans', 'hard', 'test plan', 'test planning', 'test strategy'),
  L('test scripts', 'hard', 'test script'),
  L('test data', 'hard', 'test data management'),
  L('test execution', 'hard'),
  L('test management', 'hard'),
  L('test coverage', 'hard'),
  L('defect tracking', 'hard', 'bug tracking', 'defect management', 'bug report', 'bug reports', 'defect'),
  L('triage', 'hard', 'bug triage', 'defect triage'),
  L('root cause analysis', 'hard', 'root cause', 'rca'),
  L('troubleshooting', 'hard', 'troubleshoot', 'debugging', 'debug'),
  L('release management', 'hard', 'release process', 'release readiness', 'release gatekeeping', 'release'),
  L('SDLC', 'hard', 'software development life cycle', 'software development lifecycle'),
  L('STLC', 'hard', 'software testing life cycle'),
  L('agile', 'hard', 'scrum', 'sprint', 'sprints', 'kanban'),
  L('requirements analysis', 'hard', 'requirements', 'acceptance criteria', 'user stories'),
  L('quality metrics', 'hard', 'test metrics', 'kpis', 'kpi'),
  L('log analysis', 'hard', 'console logs', 'logs'),
  L('BDD', 'hard', 'behavior driven development', 'gherkin'),
  L('TDD', 'hard', 'test driven development'),
  L('shift left', 'hard', 'shift-left testing'),
  L('compliance', 'hard', 'regulatory', 'audit', 'audits', 'hipaa', 'sox', 'gdpr', 'fda', 'iso 9001'),
  L('documentation', 'hard', 'technical documentation', 'process documentation'),

  // Testing tools
  L('Selenium', 'tool', 'selenium webdriver'),
  L('Appium', 'tool'),
  L('Cypress', 'tool'),
  L('Playwright', 'tool'),
  L('WebdriverIO', 'tool', 'webdriver io'),
  L('Puppeteer', 'tool'),
  L('Detox', 'tool'),
  L('Espresso', 'tool'),
  L('XCUITest', 'tool', 'xcuitest', 'xctest'),
  L('TestRail', 'tool'),
  L('Zephyr', 'tool'),
  L('Xray', 'tool'),
  L('qTest', 'tool'),
  L('TestFlight', 'tool'),
  L('BrowserStack', 'tool'),
  L('Sauce Labs', 'tool', 'saucelabs'),
  L('LambdaTest', 'tool'),
  L('Postman', 'tool'),
  L('SoapUI', 'tool'),
  L('Rest Assured', 'tool', 'rest-assured', 'restassured'),
  L('JMeter', 'tool'),
  L('k6', 'tool'),
  L('Gatling', 'tool'),
  L('LoadRunner', 'tool'),
  L('Cucumber', 'tool'),
  L('SpecFlow', 'tool'),
  L('Robot Framework', 'tool'),
  L('Jest', 'tool'),
  L('Mocha', 'tool'),
  L('JUnit', 'tool'),
  L('TestNG', 'tool'),
  L('pytest', 'tool'),
  L('NUnit', 'tool'),
  L('Charles Proxy', 'tool', 'charles'),
  L('Fiddler', 'tool'),
  L('Wireshark', 'tool'),
  L('Xcode', 'tool'),
  L('Android Studio', 'tool'),
  L('ADB', 'tool', 'android debug bridge'),
  L('Jira', 'tool'),
  L('Confluence', 'tool'),
  L('Azure DevOps', 'tool', 'ado', 'tfs', 'vsts'),
  L('Bugzilla', 'tool'),
  L('Asana', 'tool'),
  L('Trello', 'tool'),
  L('Figma', 'tool'),
  L('Firebase', 'tool', 'crashlytics'),
  L('Sentry', 'tool'),
  L('Datadog', 'tool'),
  L('Splunk', 'tool'),
  L('New Relic', 'tool'),
  L('Grafana', 'tool'),
  L('Kibana', 'tool', 'elk'),

  // Platforms
  L('iOS', 'hard'),
  L('Android', 'hard'),
  L('mobile', 'hard', 'mobile app', 'mobile apps', 'mobile applications'),
  L('web applications', 'hard', 'web app', 'web apps', 'web application'),
  L('macOS', 'hard', 'mac os', 'osx'),
  L('Windows', 'hard'),
  L('Linux', 'hard', 'unix'),
  L('React Native', 'hard'),
  L('Flutter', 'hard'),
  L('Swift', 'hard'),
  L('Kotlin', 'hard'),
  L('Objective-C', 'hard', 'objective c'),

  // Languages and code
  L('JavaScript', 'hard', 'js'),
  L('TypeScript', 'hard', 'ts'),
  L('Python', 'hard'),
  L('Java', 'hard'),
  L('C#', 'hard', 'c sharp', 'csharp'),
  L('.NET', 'hard', 'dotnet', 'dot net'),
  L('C++', 'hard'),
  { name: 'Go', kind: 'hard', aliases: ['golang'] },
  L('Ruby', 'hard', 'rails'),
  L('PHP', 'hard'),
  L('SQL', 'hard', 'mysql', 'postgresql', 'postgres', 'sql server', 't-sql', 'database queries'),
  L('NoSQL', 'hard', 'mongodb', 'dynamodb', 'redis'),
  L('scripting', 'hard', 'shell scripting', 'bash', 'powershell'),
  L('HTML', 'hard', 'html5'),
  L('CSS', 'hard'),
  L('React', 'hard', 'reactjs', 'react.js'),
  L('Angular', 'hard'),
  L('Node.js', 'hard', 'nodejs'),
  L('REST APIs', 'hard', 'rest api', 'restful', 'apis', 'api'),
  L('GraphQL', 'hard'),
  L('JSON', 'hard'),
  L('XML', 'hard'),
  L('microservices', 'hard', 'microservice'),
  L('OOP', 'hard', 'object oriented'),
  L('data structures', 'hard', 'algorithms'),

  // Delivery and infrastructure
  L('CI/CD', 'hard', 'ci cd', 'continuous integration', 'continuous delivery', 'continuous deployment', 'build pipelines', 'pipelines'),
  L('Jenkins', 'tool'),
  L('GitHub Actions', 'tool'),
  L('GitLab', 'tool', 'gitlab ci'),
  L('CircleCI', 'tool'),
  L('Bitbucket', 'tool'),
  L('Git', 'hard', 'github', 'version control', 'source control'),
  L('Docker', 'hard', 'containers', 'containerization'),
  L('Kubernetes', 'hard', 'k8s'),
  L('AWS', 'hard', 'amazon web services'),
  L('Azure', 'hard'),
  L('GCP', 'hard', 'google cloud'),
  L('cloud', 'hard', 'cloud platforms', 'cloud services'),
  L('DevOps', 'hard'),
  L('Terraform', 'tool'),
  L('SaaS', 'hard'),
  L('monitoring', 'hard', 'observability'),

  // Product and data
  L('product management', 'hard', 'product managers', 'product manager'),
  L('UX', 'hard', 'user experience', 'ui/ux', 'ui ux'),
  L('data analysis', 'hard', 'analytics', 'data driven', 'data-driven'),
  { name: 'Excel', kind: 'tool', aliases: ['microsoft excel', 'spreadsheets', 'google sheets'] },
  L('AI', 'hard', 'artificial intelligence', 'machine learning', 'llm', 'llms', 'generative ai', 'ai-assisted', 'ai tools'),

  // Soft skills
  L('communication', 'soft', 'communication skills', 'communicate', 'verbal and written'),
  L('collaboration', 'soft', 'collaborate', 'collaborative', 'cross-functional', 'cross functional', 'teamwork'),
  L('attention to detail', 'soft', 'detail oriented', 'detail-oriented', 'meticulous'),
  L('problem solving', 'soft', 'problem-solving', 'analytical', 'analytical skills', 'critical thinking'),
  L('leadership', 'soft', 'mentor', 'mentoring', 'mentorship'),
  L('ownership', 'soft', 'self-starter', 'self starter', 'proactive', 'initiative', 'autonomous', 'independently'),
  L('prioritization', 'soft', 'prioritize', 'time management', 'organized', 'organizational skills'),
  L('adaptability', 'soft', 'fast-paced', 'fast paced', 'adaptable'),
  L('customer focus', 'soft', 'customer-focused', 'customer focused', 'customer impact', 'user-focused', 'customer experience'),
  L('stakeholder management', 'soft', 'stakeholders', 'stakeholder'),
  L('curiosity', 'soft', 'curious', 'continuous learning', 'growth mindset'),
];

/**
 * Words written in capitals that are not skills. Company boilerplate is full of
 * them, and without this list every posting would ask for EEO and PTO.
 */
const NOT_A_SKILL = new Set([
  'A', 'AN', 'AND', 'ARE', 'AS', 'AT', 'BE', 'BY', 'FOR', 'IN', 'IS', 'IT', 'OF', 'ON', 'OR', 'THE', 'TO',
  'WE', 'YOU', 'OUR', 'ALL', 'ANY', 'NOT', 'NO', 'YES', 'IF', 'SO', 'DO', 'CAN', 'MAY', 'WILL', 'MUST',
  'US', 'USA', 'UK', 'EU', 'EEO', 'EOE', 'AA', 'ADA', 'LLC', 'INC', 'LTD', 'PLC', 'CO', 'CORP', 'GMBH',
  'PTO', 'HR', 'CEO', 'CTO', 'CFO', 'COO', 'VP', 'SVP', 'EVP', 'PM', 'AM', 'EST', 'PST', 'CST', 'MST',
  'UTC', 'GMT', 'ET', 'PT', 'CT', 'MT', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'K', 'M', 'B', 'FAQ', 'FAQS',
  'ID', 'IDS', 'OK', 'TBD', 'NA', 'N/A', 'ETC', 'EG', 'IE', 'PLEASE', 'NOTE', 'ABOUT', 'ROLE', 'TEAM',
  'JOB', 'WORK', 'NEW', 'WHO', 'WHAT', 'WHY', 'HOW', 'WHEN', 'WHERE', 'WITH', 'FROM', 'THIS', 'THAT',
  'YOUR', 'MORE', 'YEARS', 'YEAR', 'FULL', 'TIME', 'PART', 'REMOTE', 'HYBRID', 'ONSITE', 'SENIOR', 'SR',
  'JR', 'LEAD', 'STAFF', 'ENGINEER', 'QUALITY', 'MARINE', 'BENEFITS', 'REQUIREMENTS', 'RESPONSIBILITIES',
  'QUALIFICATIONS', 'SUMMARY', 'OVERVIEW', 'DESCRIPTION', 'POSITION', 'LOCATION', 'SALARY', 'COMPENSATION',
  'EXPERIENCE', 'SKILLS', 'EDUCATION', 'PREFERRED', 'REQUIRED', 'BONUS', 'EQUITY', 'DEI', 'ERG', 'ERGS',
  'LGBTQ', 'LGBTQIA', 'BIPOC', 'COVID', 'OFCCP', 'FMLA', 'FLSA', 'I', 'II', 'III', 'IV', 'V', 'X',
  'IOS', 'AI', 'QA', 'API', 'APIS', 'SQL', 'SDLC', 'STLC', 'UAT', 'BDD', 'TDD', 'AWS', 'GCP', 'SAAS',
  'CI', 'CD', 'UX', 'UI', 'OOP', 'REST', 'JSON', 'XML', 'HTML', 'CSS', 'PHP', 'ADB', 'ADO', 'TFS', 'ELK',
  'HAVE', 'HAVES', 'NICE', 'GOOD', 'GREAT', 'PLUS', 'APPLY', 'NOW', 'JOIN', 'PERKS', 'CULTURE', 'VALUES',
  'MISSION', 'DUTIES', 'DAY', 'WEEK', 'MONTH', 'OTHER', 'KEY', 'CORE', 'BASIC', 'MINIMUM', 'ADDITIONAL',
  'DESIRED', 'IDEAL', 'NEED', 'WANT', 'LIKE', 'LOVE', 'ONE', 'TWO', 'THREE', 'FIRST', 'LAST', 'NEXT',
  'DEPARTMENT', 'OFFICE', 'COMPANY', 'CANDIDATE', 'CANDIDATES', 'EMPLOYEE', 'EMPLOYEES', 'EMPLOYER',
]);

/** Lowercases, and turns every run of characters that is not a word into one space. */
function normalise(text: string): string {
  return text
    .toLowerCase()
    .replace(/[’']/g, '')
    .replace(/[^a-z0-9+#.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const patternCache = new Map<string, RegExp>();

/**
 * A pattern that matches one alias as a whole term. Letters around the term are
 * refused with lookarounds rather than \b, because \b misreads "c#" and ".net",
 * whose edges are not word characters.
 */
function patternFor(alias: string): RegExp {
  const cached = patternCache.get(alias);
  if (cached) return cached;
  const escaped = normalise(alias)
    .split(' ')
    .map((part) => part.replace(/[.*+?^${}()|[\]\\#]/g, '\\$&'))
    .join('[ ]');
  const pattern = new RegExp(`(?<![a-z0-9#+])${escaped}(?:s|es|ed|ing)?(?![a-z0-9#+])`, 'g');
  patternCache.set(alias, pattern);
  return pattern;
}

/** The first way the posting writes one of these aliases, in the posting's own case. */
function spellingIn(raw: string, aliases: readonly string[], fallback: string): string {
  for (const alias of aliases) {
    const pattern = new RegExp(patternFor(alias).source, 'i');
    const match = raw.replace(/[\u2019']/g, '').replace(/[^A-Za-z0-9+#.]+/g, ' ').match(pattern);
    if (match) return match[0];
  }
  return fallback;
}

function countIn(text: string, aliases: readonly string[]): number {
  let count = 0;
  for (const alias of aliases) {
    const matches = text.match(patternFor(alias));
    if (matches) count += matches.length;
  }
  return count;
}

/**
 * Tool and standard names the lexicon does not know, read off the posting's own
 * text: acronyms in capitals of two to six letters, and names with a capital
 * letter in the middle. Each comes back with how often the posting says it. The
 * employer's own name is left out, because a posting says it constantly and no
 * resume should.
 */
function discoveredTools(raw: string, employer: string): Map<string, number> {
  const found = new Map<string, number>();
  const employerWords = new Set(normalise(employer).split(' ').filter((w) => w !== ''));
  const acronyms = raw.match(/\b[A-Z][A-Z0-9]{1,5}\b/g) ?? [];
  const camel = raw.match(/\b[A-Z][a-z]+[A-Z][A-Za-z0-9]+\b/g) ?? [];
  for (const word of [...acronyms, ...camel]) {
    if (NOT_A_SKILL.has(word.toUpperCase())) continue;
    if (employerWords.has(normalise(word))) continue;
    if (/^[0-9]+$/.test(word)) continue;
    found.set(word, (found.get(word) ?? 0) + 1);
  }
  // A capitalised word that appears only once is as likely to be a heading or a
  // product line as a skill, so the bar is two mentions.
  for (const [word, count] of found) if (count < 2) found.delete(word);
  return found;
}

/**
 * Reads the skills a posting names and how often the resume names each one,
 * and turns that into a score.
 */
export function scoreResume(
  title: string,
  description: string,
  resume: string,
  employer = '',
): AtsReport {
  const postingText = normalise(`${title} ${description}`);
  const titleText = normalise(title);
  const resumeText = normalise(resume);

  const hits: SkillHit[] = [];
  const covered = new Set<string>();

  for (const entry of LEXICON) {
    const posting = countIn(postingText, entry.aliases);
    if (posting === 0) continue;
    for (const alias of entry.aliases) covered.add(normalise(alias));
    hits.push({
      keyword: entry.name,
      kind: entry.kind,
      posting,
      resume: countIn(resumeText, entry.aliases),
      in_title: countIn(titleText, entry.aliases) > 0,
      posting_spelling: spellingIn(`${title} ${description}`, entry.aliases, entry.name),
    });
  }

  for (const [word, posting] of discoveredTools(description, employer)) {
    if (covered.has(normalise(word))) continue;
    hits.push({
      keyword: word,
      kind: 'tool',
      posting,
      resume: countIn(resumeText, [word]),
      in_title: countIn(titleText, [word]) > 0,
      posting_spelling: word,
    });
  }

  const weightOf = (hit: SkillHit): number =>
    1 + Math.min(hit.posting - 1, 4) * 0.25 + (hit.in_title ? 1 : 0) + (hit.kind === 'soft' ? -0.5 : 0);

  let total = 0;
  let matchedWeight = 0;
  for (const hit of hits) {
    const weight = weightOf(hit);
    total += weight;
    if (hit.resume > 0) matchedWeight += weight;
  }

  const byImportance = (a: SkillHit, b: SkillHit): number =>
    weightOf(b) - weightOf(a) || a.keyword.localeCompare(b.keyword);

  return {
    score: total === 0 ? 0 : Math.round((100 * matchedWeight) / total),
    matched: hits.filter((hit) => hit.resume > 0).sort(byImportance),
    missing: hits.filter((hit) => hit.resume === 0).sort(byImportance),
  };
}
