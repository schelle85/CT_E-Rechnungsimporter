import test from "node:test";
import assert from "node:assert/strict";
import { attemptLogin, CHALLENGE_RENEWED } from "../src/login-flow.ts";

for (const cause of ["expired after 600 seconds", "deleted by configuration activation"]) {
  test(cause + ": new challenge, no automatic credential resend", async () => {
    const calls = [];
    let challenge = "stale";
    const fresh = {authenticated:false,csrf_token:"fresh"};
    const credentials = {username:"synthetic",password:"synthetic-user-password"};
    const client = {
      async login(input,csrf) { calls.push(["login",csrf]); assert.equal(input,credentials); throw {status:403}; },
      async session() { calls.push(["session"]); return fresh; },
    };
    const result = await attemptLogin(client,credentials,challenge,()=>{challenge=null;calls.push(["invalidate"]);});
    assert.deepEqual(calls,[["login","stale"],["invalidate"],["session"]]);
    assert.equal(challenge,null);
    assert.equal(result.state,fresh);
    assert.equal(result.notice,CHALLENGE_RENEWED);
    // Only an explicit second submission sends credentials again, with the new token.
    client.login=async (input,csrf)=>{calls.push(["login",csrf]);assert.equal(csrf,"fresh");return {authenticated:true,user:{role:"admin"},csrf_token:"authenticated"};};
    const second=await attemptLogin(client,credentials,result.state.csrf_token,()=>assert.fail());
    assert.equal(second.state.authenticated,true);
    assert.equal(calls.filter(x=>x[0]==="login").length,2);
  });
}
test("wrong password preserves usable challenge; no refresh or replay",async()=>{
  const denied={status:401};
  let count=0;
  await assert.rejects(attemptLogin({
    async login(){count++;throw denied;},
    async session(){assert.fail("No challenge refresh for a valid challenge");}
  },{username:"synthetic",password:"wrong"},"valid",()=>assert.fail()),error=>error===denied);
  assert.equal(count,1);
});
test("failed challenge refresh leaves state invalid and sends password once",async()=>{
  let count=0,invalid=false;
  await assert.rejects(attemptLogin({
    async login(){count++;throw {status:403};},
    async session(){throw new Error("unavailable");}
  },{username:"synthetic",password:"synthetic"},"stale",()=>{invalid=true;}),/unavailable/);
  assert.equal(count,1);assert.equal(invalid,true);
});
