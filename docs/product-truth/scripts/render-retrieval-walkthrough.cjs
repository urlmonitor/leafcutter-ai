/**
 * Render the retrieval walkthrough from canonical product-truth and the existing AC store.
 * No narrative facts are authored here; the output is an offline snapshot, not another truth store.
 * Usage: node render-retrieval-walkthrough.cjs FLOW OUTPUT REPOSITORY [TEMPLATE]
 */
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const [flowArg,outArg,repoArg,templateArg]=process.argv.slice(2);
if(!flowArg||!outArg||!repoArg)throw Error("Required: FLOW OUTPUT REPOSITORY [TEMPLATE]");
const repo=path.resolve(repoArg),output=path.resolve(outArg),input=fs.readFileSync(flowArg,"utf8").replace(/^\uFEFF/,"");
const flow=JSON.parse(input),children={},acs={};
function collect(f){
 const ids=[...f.steps.flatMap(n=>n.expands_to||[]),...[...JSON.stringify(f).matchAll(/docs\/product-truth\/flows\/([a-z0-9-]+\/[a-z0-9-]+)\.flow\.json/g)].map(m=>m[1])];
 for(const id of ids){if(id===flow.id||children[id])continue;const file=path.join(repo,"docs/product-truth/flows",id+".flow.json");children[id]=JSON.parse(fs.readFileSync(file,"utf8"));collect(children[id]);}
}
collect(flow);
const wanted=new Set([flow,...Object.values(children)].flatMap(f=>[...f.steps,...f.branches].flatMap(n=>n.implements||[])));
function visit(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isDirectory())visit(file);else if(entry.name.endsWith(".yaml")){const raw=fs.readFileSync(file,"utf8"),id=raw.match(/^id:\s*['"]?([^'"\r\n]+)['"]?\s*$/m)?.[1]?.trim();if(wanted.has(id)){acs[id]={path:path.relative(repo,file).replaceAll("\\","/"),status:raw.match(/^work_status:\s*['"]?([^'"\r\n]+)['"]?\s*$/m)?.[1]?.trim()||"not specified"};}}}}
visit(path.join(repo,"docs","acceptance-criteria"));
const css=fs.readFileSync(path.join(repo,"leafcutter-web","app","globals.css"),"utf8"),tokens=[...css.matchAll(/(--[a-z0-9-]+):\s*([^;{}]+);/g)].map(m=>m[1]+":"+m[2]).join(";");
let root=path.relative(path.dirname(output),repo).replaceAll("\\","/")+"/";
if(path.parse(output).root!==path.parse(repo).root)root="file:///"+repo.replaceAll("\\","/")+"/";
const data={flow,children,acs,repoHref:root,flowHash:crypto.createHash("sha256").update(input).digest("hex")};
const template=fs.readFileSync(templateArg||path.join(__dirname,"retrieval-walkthrough.template.html"),"utf8").replace(/^\uFEFF/,"");
const html=template.replace("__ATLAS_TOKENS__",tokens).replace("__FLOW_DATA__",JSON.stringify(data).replaceAll("<","\\u003c"));
fs.writeFileSync(output,html,"utf8");
console.log("Rendered "+flow.id+" ("+flow.steps.length+" steps, "+flow.branches.length+" branches) to "+output);

