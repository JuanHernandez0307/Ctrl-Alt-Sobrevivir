const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const root = path.resolve(__dirname, '..');
const collection = JSON.parse(fs.readFileSync(path.join(root, 'postman/collections/API_Wars_Fase1.postman_collection.json')));
const template = JSON.parse(fs.readFileSync(path.join(root, 'postman/environments/API_Wars_Sandbox.postman_environment.json')));
const items = collection.item.flatMap(folder => folder.item);
let count = 0;
function script(item, kind) {
  return item.event.find(e => e.listen === kind)?.script.exec.join('\n') || '';
}
for (const item of [collection, ...items]) {
  for (const e of item.event || []) {
    new vm.Script(e.script.exec.join('\n'), {filename: item.name || 'collection'});
    count++;
  }
}
function chain(value) {
  const result = {};
  for (const k of ['to','be','and','have']) result[k] = result;
  result.a = result.an = type => { assert.equal(typeof value, type); return result; };
  result.eql = expected => { assert.deepEqual(value, expected); return result; };
  result.include = expected => { assert.ok(value.includes(expected)); return result; };
  result.match = regexp => { assert.ok(regexp.test(value)); return result; };
  result.within = (a,b) => { assert.ok(value >= a && value <= b); return result; };
  result.lengthOf = length => { assert.equal(value.length, length); return result; };
  result.not = {};
  Object.defineProperty(result.not, 'empty', {get() { assert.ok(value.length > 0); return result; }});
  return result;
}
function context(item, initial={}, data={}, code=200, headers={}) {
  const values = Object.fromEntries(template.values.map(v => [v.key,v.value]));
  Object.assign(values, initial);
  const tests = [];
  const state = {skipped:false,stopped:false,delays:[]};
  function replace(text) {
    return text.replace(/\{\{([^{}]+)\}\}/g, (_, k) => k === '$guid' ? '11111111-2222-4333-8444-555555555555' : (values[k] ?? '{{' + k + '}}'));
  }
  const pm = {
    environment:{get:k=>values[k],set:(k,v)=>{values[k]=String(v);},unset:k=>{delete values[k];}},
    variables:{replaceIn:replace},
    request:{url:{toString:()=>item.request?.url || 'https://api-sandbox.factus.com.co/v2/bills/validate'}},
    response:{code,json:()=>data,headers:{get:name=>headers[name] ?? null}},
    execution:{skipRequest:()=>{state.skipped=true;},setNextRequest:()=>{state.stopped=true;}},
    test:(name,fn)=>{try {fn();tests.push({name,ok:true});}catch(e){tests.push({name,ok:false,error:e.message});}},
    expect:chain
  };
  return {values,tests,state,sandbox:{pm,console:{error(){},warn(){}},setTimeout:(_,ms)=>{state.delays.push(ms);},Date,Number,String,Math,JSON,Array,Object,Error}};
}
function run(ctx, src) { return vm.runInNewContext(src,ctx.sandbox,{timeout:3000}); }
function item(name) { const i = items.find(i=>i.name===name); assert.ok(i,name); return i; }
function ok(ctx) { assert.deepEqual(ctx.tests.filter(t=>!t.ok),[]); }
const checks = [];
function check(name,fn) {fn();checks.push(name);}
check('OAuth usa expires_in real y guarda ambos tokens',()=>{
 const i=item('Factus - obtener token (manual)');
 const c=context(i,{}, {access_token:'token-demo',refresh_token:'refresh-demo',expires_in:123,token_type:'Bearer'});
 const start=Date.now();run(c,script(i,'test'));ok(c);
 assert.ok(Number(c.values.factus_expires_at_ms)>=start+123000);
 assert.equal(c.values.factus_refresh_token,'refresh-demo');
});
check('Pay conserva referencia en reintentos',()=>{
 const i=item('Factus Pay - crear recaudo Sandbox');const c=context(i,{pay_token:'token-demo'});
 run(c,script(i,'prerequest'));const ref=c.values.order_reference;run(c,script(i,'prerequest'));assert.equal(c.values.order_reference,ref);
});
check('Token Pay existente bloquea reautenticacion accidental',()=>{
 const i=item('Factus Pay - obtener token (un responsable)');const c=context(i,{pay_token:'token-demo',pay_email:'demo@example.com',pay_password:'fixture'});
 assert.throws(()=>run(c,script(i,'prerequest')),/Ya tienes pay_token/);assert.ok(c.state.skipped);
});
check('Pay ready limpia evidencia anterior y no permite facturar',()=>{
 const i=item('Factus Pay - consultar y verificar pago');const c=context(i,{pay_token:'token-demo',order_reference:'APIW-TEST',pay_verified_reference:'OLD'},{data:{reference_code:'APIW-TEST',amount:119000,status:'ready'}});
 run(c,script(i,'prerequest'));run(c,script(i,'test'));ok(c);assert.equal(c.values.pay_verified_reference,undefined);
});
check('Pago con monto distinto no genera evidencia',()=>{
 const i=item('Factus Pay - consultar y verificar pago');const c=context(i,{pay_token:'token-demo',order_reference:'APIW-TEST'},{data:{reference_code:'APIW-TEST',amount:1000,status:'paid'}});
 run(c,script(i,'prerequest'));run(c,script(i,'test'));assert.ok(c.tests.some(t=>!t.ok));assert.equal(c.values.pay_verified_reference,undefined);
});
check('Factura se bloquea sin pago y se permite tras consulta paid concordante',()=>{
 const fact=item('Factus V2 - emitir factura tras pago verificado');const bad=context(fact,{factus_access_token:'token-demo',order_reference:'APIW-TEST',numbering_range_id:'10'});
 assert.throws(()=>run(bad,script(fact,'prerequest')),/pay_verified_reference/);assert.ok(bad.state.skipped);
 const pay=item('Factus Pay - consultar y verificar pago');const paid=context(pay,{order_reference:'APIW-TEST',pay_token:'token-demo'},{data:{reference_code:'APIW-TEST',amount:119000,status:'paid'}});
 run(paid,script(pay,'prerequest'));run(paid,script(pay,'test'));ok(paid);
 const good=context(fact,{...paid.values,factus_access_token:'token-demo',numbering_range_id:'10'});run(good,script(fact,'prerequest'));assert.equal(good.state.skipped,false);
 const body=JSON.parse(good.sandbox.pm.variables.replaceIn(fact.request.body.raw));
 assert.equal(Number(body.payment_details[0].amount),119000);
 assert.equal(body.customer.identification_document_code,'41');
 assert.equal(body.customer.municipality_code,undefined);
});
check('HTTP429 aplica Retry-After y bloquea siguiente envio al proveedor',()=>{
 const i=item('Factus Pay - consultar y verificar pago');const c=context(i,{order_reference:'APIW-TEST'}, {},429,{'Retry-After':'120'});
 run(c,script(collection,'test'));assert.ok(c.state.stopped);assert.ok(Number(c.values['cooldown_pay-api-sandbox.factus.com.co'])>=Date.now()+119000);
 assert.throws(()=>run(c,script(collection,'prerequest')),/cooldown/);assert.ok(c.state.skipped);
});
check('No permite hosts de produccion ni destinos arbitrarios',()=>{
 const fake={request:{url:'https://api.factus.com.co/v2/bills/validate'}};const c=context(fake);
 assert.throws(()=>run(c,script(collection,'prerequest')),/Host no autorizado/);assert.ok(c.state.skipped);
});
check('Discovery sin resultados no inventa ID o precio',()=>{
 const i=item('Ticketmaster - buscar conciertos');const c=context(i,{tm_event_id:'old',tm_reference_price:'100'},{page:{totalElements:0}});
 run(c,script(i,'test'));assert.equal(c.values.tm_event_id,undefined);assert.equal(c.values.tm_reference_price,undefined);
});
check('ExchangeRate detecta error semantico aun con HTTP200',()=>{
 const i=item('ExchangeRate - todas las tasas desde COP');const c=context(i,{}, {result:'error','error-type':'quota-reached'});
 run(c,script(i,'test'));assert.ok(c.tests.some(t=>!t.ok));assert.ok(c.state.stopped);
});
check('ExchangeRate calcula cinco divisas desde una respuesta',()=>{
 const i=item('ExchangeRate - todas las tasas desde COP');const c=context(i,{}, {result:'success',base_code:'COP',conversion_rates:{USD:0.00025,EUR:0.00022,GBP:0.00019,MXN:0.005,CAD:0.00035},time_last_update_unix:100,time_next_update_unix:200});
 run(c,script(i,'test'));ok(c);const display=JSON.parse(c.values.fx_display_amounts);assert.equal(Object.keys(display).length,5);assert.equal(display.USD,'29.75');
});
check('Varios rangos requieren seleccion explicita',()=>{
 const i=item('Factus V2 - rangos activos de factura');const c=context(i,{}, {data:[{id:10,is_active:true,current:1,to:100},{id:20,is_active:true,current:1,to:100}]});
 run(c,script(i,'test'));assert.ok(c.tests.some(t=>!t.ok));assert.equal(c.values.numbering_range_id,undefined);
});
console.log(JSON.stringify({scriptsCompiled:count,checks:checks.length,passed:checks,liveRequests:0},null,2));
