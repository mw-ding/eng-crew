// Builds an ExcalidrawElementSkeleton[] for the Eng Crew diagram.
const FONT = 5; // Excalifont (hand-drawn)
const C = (i) => 380 + (i - 1) * 320; // column centers
const LANES = [
  { id: "md",    name: "MD\n(human)",              sub: "decisions,\n/crew commands", h: 200, fill: "#ffc9c9", bg: "#fff5f5", stroke: "#c92a2a" },
  { id: "ash",   name: "Ash\n(CTO /\ncoordinator)", sub: "", h: 230, fill: "#d0bfff", bg: "#f8f0fc", stroke: "#6741d9" },
  { id: "riley", name: "Riley\n(researcher)",       sub: "", h: 150, fill: "#a5d8ff", bg: "#e7f5ff", stroke: "#1971c2" },
  { id: "gh",    name: "GitHub",                    sub: "issues · PRs · CI\nlabels · markers", h: 260, fill: "#dee2e6", bg: "#f1f3f5", stroke: "#495057" },
  { id: "ben",   name: "Ben\n(builder)",            sub: "", h: 230, fill: "#b2f2bb", bg: "#ebfbee", stroke: "#2f9e44" },
  { id: "vera",  name: "Vera\n(reviewer-\nvalidator, md-mt)", sub: "", h: 190, fill: "#ffec99", bg: "#fff9db", stroke: "#e67700" },
  { id: "sam",   name: "Sam\n(synthesizer)",        sub: "", h: 190, fill: "#ffd8a8", bg: "#fff4e6", stroke: "#d9480f" },
];
const LANE_X = 0, LANE_W = 2920, TOP = 130;
const lane = {};
let y = TOP;
for (const l of LANES) { lane[l.id] = { ...l, y, cy: y + l.h / 2 }; y += l.h; }
const LANES_BOTTOM = y;

const els = [];
const nodes = {};
// title
els.push({ type: "text", x: 0, y: 30, text: "Eng Crew: event-driven PR pipeline", fontSize: 52, fontFamily: FONT, strokeColor: "#1e1e1e" });
els.push({ type: "text", x: 900, y: 50, text: "one issue → one branch → one PR → one squash merge", fontSize: 26, fontFamily: FONT, strokeColor: "#495057" });

// lanes
for (const l of Object.values(lane)) {
  els.push({ type: "rectangle", id: `lane-${l.id}`, x: LANE_X, y: l.y, width: LANE_W, height: l.h,
    backgroundColor: l.bg, fillStyle: "solid", strokeColor: "#ced4da", strokeWidth: 1, roughness: 1, opacity: 100, locked: true });
  els.push({ type: "rectangle", id: `lanehdr-${l.id}`, x: LANE_X, y: l.y, width: 210, height: l.h,
    backgroundColor: l.fill, fillStyle: "hachure", strokeColor: l.stroke, strokeWidth: 1, roughness: 1, locked: true });
  const t = l.name + (l.sub ? "\n" + l.sub : "");
  els.push({ type: "text", x: 14, y: l.cy - (t.split("\n").length * 25) / 2, text: t, fontSize: 20, fontFamily: FONT, strokeColor: l.stroke, locked: true });
}

function node(id, laneId, cx, text, { w = 250, h = 120, fs = 19, dy = 0 } = {}) {
  const l = lane[laneId];
  const n = { type: "rectangle", id, x: cx - w / 2, y: l.cy - h / 2 + dy, width: w, height: h,
    backgroundColor: l.fill, fillStyle: "solid", strokeColor: l.stroke, strokeWidth: 2, roughness: 1,
    roundness: { type: 3 }, label: { text, fontSize: fs, fontFamily: FONT, strokeColor: "#1e1e1e" } };
  nodes[id] = n; els.push(n); return n;
}
// geometry helpers
const L = (id) => nodes[id].x, R = (id) => nodes[id].x + nodes[id].width;
const T = (id) => nodes[id].y, B = (id) => nodes[id].y + nodes[id].height;
const MX = (id) => nodes[id].x + nodes[id].width / 2, MY = (id) => nodes[id].y + nodes[id].height / 2;

// ---- nodes
node("md_spec", "md", C(1), "MD + Ash finalize\nthe spec");
node("md_cmd", "md", C(4), "/crew commands on a PR:\nhold · resume · rework\nrereview · merge-ok · escalate", { w: 320, h: 130 });
node("md_esc", "md", 1990, "MD decides on\nescalations", { w: 240, h: 100 });

node("ash_spec", "ash", C(1), "1. Spec\ndocs/specs + sub-specs", { h: 110 });
node("ash_issues", "ash", C(2), "2. Opens issues,\nlabels one crew:ready,\nassigns mw-ding", { w: 260, h: 130 });
node("ash_disp", "ash", C(4), "/crew steering\ndispatcher", { w: 240, h: 100 });
node("ash_esc", "ash", 1730, "Escalations\n(Ash triages,\nthen MD)", { w: 210, h: 120 });
node("ash_sweep", "ash", 2140, "Stuck-PR sweeper\n(hourly)", { w: 230, h: 100 });
node("ash_merge", "ash", 2680, "After-merge routine:\nreleases next\nunblocked issues\n(back to step 2)", { w: 270, h: 150 });

node("riley", "riley", C(1), "Background research\nfor specs", { w: 250, h: 90 });

node("gh_issue", "gh", C(2), "Issue\ncrew:ready\nassigned", { w: 200, h: 120 });
node("gh_pr", "gh", C(3), "PR (non-draft)\nCloses #n + evidence\ncrew:in-review", { w: 260, h: 130 });
node("gh_ci", "gh", C(4), "4. CI runs", { w: 220, h: 90 });
node("gh_verdict", "gh", 1990, "6. One verdict\nAPPROVE or\nREQUEST_CHANGES\n(review marker)", { w: 250, h: 160 });
node("gh_nudge", "gh", 2250, "Nudge on stalled PR\n(≤3 nudges)", { w: 230, h: 90 });
node("gh_merged", "gh", 2680, "Squash-merged\n(pr-merged)", { w: 220, h: 100 });

node("ben_build", "ben", C(3), "3. Worker builds,\nopens PR with evidence\n≤5 workers in parallel\nClaude Code → Codex fallback", { w: 300, h: 160 });
node("ben_fix", "ben", 1700, "7a. Fixes & pushes\n(same branch)\nmax 3 review rounds\n+ max 3 ci-fixes", { w: 250, h: 150 });

node("vera", "vera", C(4), "5. Review pass, then\nseparate validation pass\n(engine ≠ builder's)", { w: 300, h: 130 });

node("sam", "sam", 1990, "7b. Checks merge gate,\nserial squash merge,\nupdate-branch behind PRs", { w: 300, h: 130 });

// ---- arrows
const STY = {
  wake: { strokeColor: "#1e1e1e", strokeWidth: 2.5, strokeStyle: "solid" },
  msg:  { strokeColor: "#c2255c", strokeWidth: 2.5, strokeStyle: "dashed" },
  write:{ strokeColor: "#868e96", strokeWidth: 2, strokeStyle: "dotted" },
};
function arrow(kind, from, to, pts, label, { both = false, fs = 18 } = {}) {
  const [x0, y0] = pts[0];
  const a = { type: "arrow", x: x0, y: y0, points: pts.map(([x, yy]) => [x - x0, yy - y0]),
    ...STY[kind], roughness: 1, endArrowhead: "arrow", startArrowhead: both ? "arrow" : null,
    start: { id: from }, end: { id: to } };
  if (label) a.label = { text: label, fontSize: fs, fontFamily: FONT, strokeColor: STY[kind].strokeColor === "#868e96" ? "#495057" : STY[kind].strokeColor };
  els.push(a); return a;
}
arrow("msg", "md_spec", "ash_spec", [[MX("md_spec"), B("md_spec")], [MX("ash_spec"), T("ash_spec")]], "1. finalize spec", { both: true });
arrow("msg", "ash_spec", "riley", [[MX("ash_spec"), B("ash_spec")], [MX("riley"), T("riley")]], "research on request", { both: true });
arrow("write", "ash_spec", "ash_issues", [[R("ash_spec"), MY("ash_spec")], [L("ash_issues"), MY("ash_spec")]], null);
arrow("write", "ash_issues", "gh_issue", [[MX("ash_issues"), B("ash_issues")], [MX("gh_issue"), T("gh_issue")]], "2. label + assign");
arrow("wake", "gh_issue", "ben_build", [[MX("gh_issue"), B("gh_issue")], [MX("gh_issue"), MY("ben_build")], [L("ben_build"), MY("ben_build")]], "3. issue-assigned");
arrow("write", "ben_build", "gh_pr", [[MX("ben_build"), T("ben_build")], [MX("gh_pr"), B("gh_pr")]], "opens PR");
arrow("write", "gh_pr", "gh_ci", [[R("gh_pr"), MY("gh_ci")], [L("gh_ci"), MY("gh_ci")]], null);
// CI -> Vera (ci-passed) straight down through the empty Ben slot
arrow("wake", "gh_ci", "vera", [[MX("gh_ci") - 40, B("gh_ci")], [MX("gh_ci") - 40, T("vera")]], "5. ci-passed");
// CI -> Ben fix (ci-failed)
arrow("wake", "gh_ci", "ben_fix", [[R("gh_ci"), MY("gh_ci") - 15], [MX("ben_fix") - 40, MY("gh_ci") - 15], [MX("ben_fix") - 40, T("ben_fix")]], "ci-failed\n(ci-fix)");
// Ben fix -> CI (push)
arrow("write", "ben_fix", "gh_ci", [[L("ben_fix"), MY("ben_fix")], [MX("gh_ci") + 60, MY("ben_fix")], [MX("gh_ci") + 60, B("gh_ci")]], "push → CI again");
// Vera -> verdict
arrow("write", "vera", "gh_verdict", [[R("vera"), MY("vera")], [MX("gh_verdict") - 60, MY("vera")], [MX("gh_verdict") - 60, B("gh_verdict")]], "6. formal review");
// verdict -> Ben fix (changes requested)
arrow("wake", "gh_verdict", "ben_fix", [[L("gh_verdict"), B("gh_verdict") - 25], [R("ben_fix") - 30, T("ben_fix")]], "7a. changes\nrequested");
// verdict -> Sam
arrow("wake", "gh_verdict", "sam", [[MX("gh_verdict") + 60, B("gh_verdict")], [MX("gh_verdict") + 60, T("sam")]], "7b. review-approved");
// Sam -> merged
arrow("write", "sam", "gh_merged", [[R("sam"), MY("sam")], [MX("gh_merged"), MY("sam")], [MX("gh_merged"), B("gh_merged")]], "squash-merge");
// merged -> Ash after-merge
arrow("wake", "gh_merged", "ash_merge", [[MX("gh_merged"), T("gh_merged")], [MX("gh_merged"), B("ash_merge")]], "8. pr-merged");
// /crew commands -> dispatcher
arrow("wake", "md_cmd", "ash_disp", [[MX("ash_disp"), B("md_cmd")], [MX("ash_disp"), T("ash_disp")]], "pr-comment");
// dispatcher -> PR (hand-off)
arrow("write", "ash_disp", "gh_pr", [[L("ash_disp") + 30, B("ash_disp")], [MX("gh_pr") + 60, T("gh_pr")]], "steer label /\nreview marker");
// escalation: Ben fix -> Ash escalations
arrow("msg", "ben_fix", "ash_esc", [[MX("ben_fix") + 30, T("ben_fix")], [MX("ben_fix") + 30, B("ash_esc")]], "after 3 rounds:\nescalate");
// Ash esc -> MD
arrow("msg", "ash_esc", "md_esc", [[MX("ash_esc"), T("ash_esc")], [L("md_esc") + 30, B("md_esc")]], "escalate");
// sweeper -> MD, sweeper -> nudge
arrow("msg", "ash_sweep", "md_esc", [[MX("ash_sweep") - 20, T("ash_sweep")], [R("md_esc") - 40, B("md_esc")]], "after 3\nnudges");
arrow("msg", "ash_sweep", "gh_nudge", [[MX("ash_sweep") + 60, B("ash_sweep")], [MX("ash_sweep") + 60, T("gh_nudge")]], "re-wake whichever\nbot stalled");

// ---- legend + note
const LY = LANES_BOTTOM + 40;
els.push({ type: "rectangle", id: "legend", x: 0, y: LY, width: 820, height: 200, backgroundColor: "#ffffff", fillStyle: "solid", strokeColor: "#868e96", strokeWidth: 1, roughness: 1, roundness: { type: 3 } });
els.push({ type: "text", x: 20, y: LY + 12, text: "Legend", fontSize: 24, fontFamily: FONT, strokeColor: "#1e1e1e" });
const leg = [["wake", "solid arrow = GitHub event wakes a bot"], ["msg", "dashed = message or escalation"], ["write", "dotted grey = bot writes to GitHub (PR, label, review)"]];
leg.forEach(([k, t], i) => {
  const yy = LY + 70 + i * 45;
  els.push({ type: "arrow", x: 30, y: yy, points: [[0, 0], [130, 0]], ...STY[k], roughness: 1, endArrowhead: "arrow", startArrowhead: null });
  els.push({ type: "text", x: 185, y: yy - 13, text: t, fontSize: 21, fontFamily: FONT, strokeColor: "#1e1e1e" });
});
els.push({ type: "text", x: 900, y: LY + 60, text: "All handoffs happen on GitHub (labels, review markers); no bot relays through chat.", fontSize: 30, fontFamily: FONT, strokeColor: "#1e1e1e" });
els.push({ type: "text", x: 900, y: LY + 115, text: "Loops are bounded: ≤3 verdict rounds, ≤3 ci-fixes, ≤3 sweeper nudges, then Ash → MD.", fontSize: 22, fontFamily: FONT, strokeColor: "#495057" });

export default els;
