import {test} from "node:test";
import assert from "node:assert/strict";
import {isOperationsStatus,scheduleStateMatches,freshnessDeadline,freshStatus,stateLabel,jobReason} from "../src/operations.ts";
import {api,ApiProtocolError} from "../src/api.ts";
import {activeStatus,unknownStatus,now} from "./operations-fixture.mjs";

test("active, configured paused and unknown remain separate validated states",()=>{
  const active=activeStatus(),paused=activeStatus(),unknown=unknownStatus();
  Object.assign(paused,{state:"paused",automatic_schedule_active:false,automatic_schedule_state:"paused"});
  for(const row of Object.values(paused.jobs))Object.assign(row,{active:false,state:"paused"});
  for(const value of [active,paused,unknown])assert.equal(isOperationsStatus(value),true);
  assert.equal(paused.jobs.inbox.configured,true);assert.equal(unknown.automatic_schedule_active,null);
  assert.equal(stateLabel.unknown,"Nicht prüfbar");assert.equal(scheduleStateMatches(false,"unknown"),false);
});
test("invalid freshness, booleans, hidden fields and contradictory green states fail closed",()=>{
  for(const mutate of [v=>v.schema_version=true,v=>v.private_profile="secret",v=>v.expires_at++,v=>v.generated_at=now-181,
    v=>v.checked_at=now-31,v=>v.boot_id="invalid",v=>v.jobs.inbox.active="true",v=>v.jobs.inbox.configured=false,
    v=>v.jobs.inbox.last_result=["ok"],v=>v.jobs.inbox.next_run_at=Number.MAX_SAFE_INTEGER,v=>v.mounts.importer=null,
    v=>v.startup.ready=false,v=>v.draining=true,v=>v.jobs.inbox.blocked=true,v=>v.automatic_schedule_active=false]){
    const value=activeStatus();mutate(value);assert.equal(isOperationsStatus(value),false);
  }
  const invalid=unknownStatus();invalid.jobs.inbox.active=false;assert.equal(isOperationsStatus(invalid),false);
});
test("active timer with failed processing prerequisites is degraded; notifications remain independent",()=>{
  const value=activeStatus();value.mounts.importer=null;value.state="degraded";
  value.jobs.inbox.state=value.jobs.corrections.state="degraded";
  assert.equal(isOperationsStatus(value),true);assert.equal(value.jobs.notifications.state,"active");
});
test("shared queue deferral explains waiting without claiming successful processing or changing the schema",()=>{
  for(const name of ["inbox","corrections"]){
    const value=activeStatus();value.jobs[name].last_result="deferred";
    assert.equal(isOperationsStatus(value),true);
    assert.match(jobReason(name,value.jobs[name]),/teilen sich die Verarbeitung/);
    assert.match(jobReason(name,value.jobs[name]),/nächste Startgelegenheit zurückgestellt/);
    for(const outcome of ["ok","failed","unknown","none"]){
      value.jobs[name].last_result=outcome;assert.equal(jobReason(name,value.jobs[name]),null);
    }
  }
  const value=activeStatus();value.jobs.tls.last_result="deferred";
  assert.equal(jobReason("tls",value.jobs.tls),null);
});
test("monotonic freshness subtracts transit time and expires without another response",()=>{
  const value=activeStatus(),deadline=freshnessDeadline(value,0,5000);
  assert.equal(deadline,180000);assert.equal(freshStatus(value,deadline,179999),value);assert.equal(freshStatus(value,deadline,180000),null);
  assert.equal(freshStatus(value,deadline,999999),null);assert.equal(freshnessDeadline(unknownStatus(),0,5000),5000);
  const late=activeStatus();late.checked_at=now+180;assert.equal(freshStatus(late,freshnessDeadline(late,0,1),1),null);
});
test("status API accepts only full checked projections and never sends a control request",async t=>{
  const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original});let calls=0;
  for(const value of [activeStatus(),unknownStatus(),{}, {...activeStatus(),state:"paused"}]){
    globalThis.fetch=async(path,options)=>{calls++;assert.equal(path,"/api/operations/status");assert.equal(options.cache,"no-store");assert.equal(options.body,undefined);assert.equal(options.method,undefined);return new Response(JSON.stringify(value),{status:200})};
    if(isOperationsStatus(value))assert.deepEqual(await api("/api/operations/status"),value);
    else await assert.rejects(api("/api/operations/status"),ApiProtocolError);
  }
  assert.equal(calls,4);
});
test("notification config GET/PUT validate nullable flags and the matching state",async t=>{
  const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original});
  for(const [active,state,valid] of [[null,"unknown",true],[false,"paused",true],[true,"active",true],[true,"degraded",true],[false,"active",false],[null,"paused",false],[false,undefined,false]]){
    globalThis.fetch=async()=>new Response(JSON.stringify({version:1,scope_key:"a".repeat(64),configured:true,can_edit:true,settings:{recipients:[]},automatic_schedule_active:active,automatic_schedule_state:state}),{status:200});
    for(const options of [{},{method:"PUT",body:"{}"}]){
      if(valid)assert.equal((await api("/api/notifications/config",options)).automatic_schedule_active,active);
      else await assert.rejects(api("/api/notifications/config",options),ApiProtocolError);
    }
  }
});
