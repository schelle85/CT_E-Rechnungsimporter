export const now=1794835000;
export function activeStatus(){
  return {schema_version:1,state:"active",reason:null,checked_at:now,generated_at:now,expires_at:now+180,
    source_commit:"a".repeat(40),deployment_id:"11111111-1111-1111-1111-111111111111",instance_id:"22222222-2222-2222-2222-222222222222",boot_id:"33333333-3333-3333-3333-333333333333",timezone:"Europe/Berlin",draining:false,processing_running:false,
    startup:{configured:true,active:true,ready:true,database_ready:true,nginx_ready:true,last_result:"ok",last_run_at:now-60},mounts:{importer:true,tls_source:true},
    jobs:Object.fromEntries(["inbox","corrections","notifications","tls"].map(name=>[name,{configured:true,active:true,running:false,blocked:false,last_result:"ok",last_run_at:now-60,next_run_at:now+60,state:"active"}])),
    automatic_schedule_active:true,automatic_schedule_state:"active"};
}
export function unknownStatus(){
  const value=activeStatus();
  for(const key of ["generated_at","expires_at","source_commit","deployment_id","instance_id","boot_id","draining","processing_running","automatic_schedule_active"])value[key]=null;
  Object.assign(value,{state:"unknown",reason:"missing",automatic_schedule_state:"unknown"});
  for(const key of Object.keys(value.startup))value.startup[key]=key==="last_result"?"unknown":null;
  value.mounts={importer:null,tls_source:null};
  for(const row of Object.values(value.jobs))for(const key of Object.keys(row))row[key]=["state","last_result"].includes(key)?"unknown":null;
  return value;
}
