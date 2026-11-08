// Source-only probes for an existing Playwright-capable browser host after approval.
// No application dependency or runtime auth bypass; all fixtures are test-only routes.
import assert from "node:assert/strict";
import { CHALLENGE_RENEWED } from "../src/login-flow.ts";

const user={guid:"1".repeat(32),dn:"CN=Synthetic,DC=example,DC=invalid",username:"synthetic",role:"admin"};
export async function checkExpiredLoginChallenge(page,url,cause="expired") {
  await page.setViewportSize({width:1280,height:900});
  let challenges=0,posts=0;
  await page.route("**/api/**",async route=>{
    const path=new URL(route.request().url()).pathname;
    const reply=data=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(data)});
    if(path==="/api/auth/session"){challenges++;return reply({authenticated:false,csrf_token:challenges===1?"stale":"fresh"});}
    if(path==="/api/auth/login"){
      posts++;
      if(posts===1)return route.fulfill({status:403,contentType:"application/json",body:JSON.stringify({detail:cause+" challenge rejected"})});
      assert.equal(route.request().headers()["x-csrf-token"],"fresh");
      return reply({authenticated:true,user,csrf_token:"signed-in"});
    }
    if(path==="/api/demo/processes")return reply({synthetic:true,items:[]});
    return reply({status:"ready"});
  });
  await page.goto(url);
  await page.getByLabel("Benutzername oder UPN").fill("synthetic");
  await page.getByLabel(/^Kennwort(?:\s*\*)?$/).fill("synthetic-user-password");
  await page.getByRole("button",{name:"Anmelden",exact:true}).click();
  await page.getByText(CHALLENGE_RENEWED,{exact:true}).waitFor();
  assert.equal(posts,1);assert.equal(challenges,2);
  assert.equal(await page.getByLabel(/^Kennwort(?:\s*\*)?$/).inputValue(),"");
  await page.getByLabel(/^Kennwort(?:\s*\*)?$/).fill("synthetic-user-password");
  await page.getByRole("button",{name:"Anmelden",exact:true}).click();
  await page.getByRole("button",{name:"Abmelden",exact:true}).waitFor();
  assert.equal(posts,2);
  await page.unroute("**/api/**");
}
export async function checkReaderSettings(page,url) {
  await page.setViewportSize({width:1280,height:900});
  const settings={servers:["dc.example.invalid"],port:636,search_base:"DC=example,DC=invalid",bind_user:"ldap@example.invalid",admin_group:"CN=Admins,DC=example,DC=invalid",reader_group:"CN=Readers,DC=example,DC=invalid",connect_timeout:3,receive_timeout:5};
  let writes=0;
  await page.route("**/api/**",async route=>{
    if(route.request().method()!=="GET")writes++;
    const path=new URL(route.request().url()).pathname;
    const data=path==="/api/auth/session"?{authenticated:true,user:{...user,role:"reader"},csrf_token:"reader-csrf"}:
      path==="/api/admin/config"?{version:1,settings,password_set:true,can_edit:false}:
      path==="/api/admin/audit"?{items:[]}:
      path==="/api/demo/processes"?{synthetic:true,items:[]}:{status:"ready"};
    return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(data)});
  });
  await page.goto(url);
  await page.getByRole("button",{name:"Administration",exact:true}).click();
  await page.getByText("dc.example.invalid",{exact:true}).waitFor();
  await page.getByRole("heading",{name:"Änderungs- und Zugriffsprotokoll"}).waitFor();
  assert.equal(await page.locator('input[type="password"]').count(),0);
  assert.equal(await page.getByRole("button",{name:"Prüfen und aktivieren"}).count(),0);
  assert.equal(await page.locator("main input, main textarea, main select").count(),0);
  assert.equal(writes,0);
  await page.unroute("**/api/**");
}
