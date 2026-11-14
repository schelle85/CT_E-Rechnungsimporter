import assert from "node:assert/strict";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { queuePending, readPending, receiptMatches, rejectPending, resolvePending, intentPath } from "../src/pending-intents.ts";
const messageId="a".repeat(64), targetId="b".repeat(64);
const memory=()=>{const values=new Map();return {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}};
const approval=()=>({kind:"approve",messageId,targetId,payload:{request_id:"approval-uuid",expected_revision:0,finding_revision:0,finding_key:"c".repeat(64),source_sha256:"d".repeat(64),decision:"Mahnung"}});
const retry=()=>({kind:"retry",messageId,targetId:messageId,payload:{request_id:"retry-uuid",expected_revision:0}});
for(const make of [approval,retry])test(make().kind+" response loss freezes full payload across detail reload and new revision",()=>{
  const storage=memory(),original=make();queuePending(storage,"same-guid",original);
  original.payload.expected_revision=99;
  const reloaded=readPending(storage,"same-guid",messageId);
  assert.equal(reloaded.payload.expected_revision,0);
  const next=make();next.payload.expected_revision=1;next.payload.request_id="different-request";
  assert.deepEqual(queuePending(storage,"same-guid",next),reloaded);
  assert.deepEqual(readPending(storage,"same-guid",messageId),reloaded);
  assert.equal(readPending(storage,"other-guid",messageId),null);
  assert.ok(intentPath(reloaded).startsWith("/api/"));
  const marked=rejectPending(storage,"same-guid",reloaded);
  assert.deepEqual(marked.payload,reloaded.payload);
  resolvePending(storage,"same-guid",messageId);
  assert.equal(queuePending(storage,"same-guid",next).payload.expected_revision,1);
});
test("matching server receipt is bound to original request and target",async()=>{
  for(const intent of [approval(),retry()]){
    const key=createHash("sha256").update(JSON.stringify([intent.targetId,intent.payload.request_id])).digest("hex");
    const receipt=intent.kind==="approve"?{correction_key:key,attachment_key:targetId,decision:"Mahnung"}:{request_key:key,message_key:messageId,expected_revision:0};
    assert.equal(await receiptMatches(intent,receipt),true);
    assert.equal(await receiptMatches({...intent,payload:{...intent.payload,request_id:"different-id"}},receipt),false);
  }
});
test("storage refusal prevents sending an untracked new intent",()=>{
  assert.throws(()=>queuePending({getItem:()=>null,setItem:()=>{throw new Error("unavailable")},removeItem:()=>{}},"guid",retry()),/unavailable/);
});