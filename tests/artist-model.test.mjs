import test from 'node:test';
import assert from 'node:assert/strict';
import {PARTS,SIZES,defaultConfig,normalizeConfig,validateEnvelope,canonicalTemplate,transformPixels,fitRect,crc32,zipFiles} from '../docs/artist/model.mjs';

test('same nine component keys and 46 allowed paths as Studio',()=>{
  assert.equal(Object.keys(PARTS).length,9);assert.equal(Object.keys(SIZES).length,46);
  assert.deepEqual(SIZES['/res/Other/dark/sport/bg0_1.png'],[468,518]);
});
test('color transformation preserves alpha, transparent RGB and red pixels',()=>{
  const input=new Uint8ClampedArray([255,255,255,180,240,20,5,255,45,80,99,0,90,120,180,127]);
  const out=transformPixels(input,{color:'#32c880',opacity:100},true);
  assert.deepEqual([...out],[50,200,128,180,240,20,5,255,45,80,99,0,35,141,90,127]);
});
test('background tint uses Studio integer luma, alpha rounding and clipping',()=>{
  assert.deepEqual([...transformPixels(new Uint8ClampedArray([255,255,255,255]),{color:'#afafaf',opacity:45})],[238,238,238,115]);
});
test('cover/contain/stretched crop respects original image contract',()=>{
  assert.deepEqual(fitRect(200,100,100,100,'cover',0,1),[0,0,100,100,0,0,100,100]);
  assert.deepEqual(fitRect(200,100,100,100,'contain'),[0,0,200,100,0,25,100,50]);
  assert.deepEqual(fitRect(200,100,100,100,'stretch'),[0,0,200,100,0,0,100,100]);
});
test('reject malformed config and protected component edits',()=>{
  for(const parts of [{evil:{}},{ring:{enabled:'yes'}},{left:{color:'red'}},{ring:{x:NaN}},{speed:{mode:'image'}},{rpm_accent:{opacity:50}},{left:{image:'https://evil.invalid/a.png'}}])assert.throws(()=>normalizeConfig({parts}));
  assert.throws(()=>normalizeConfig(JSON.parse('{"parts":{"__proto__":{}}}')));
});
test('template name matching is allowlisted and cannot traverse',()=>{
  assert.equal(canonicalTemplate('templates/res_sport/SPORT_NIGHT_BG_24.png'),'/res_sport/SPORT_NIGHT_BG_24.png');
  for(const path of ['../res_sport/SPORT_NIGHT_BG_24.png','res_sport\\SPORT_NIGHT_BG_24.png','anything.svg','session.json'])assert.equal(canonicalTemplate(path),null);
});
test('portable envelope rejects missing images and untrusted image IDs',()=>{
  const config=defaultConfig();Object.assign(config.parts.wallpaper,{enabled:true,mode:'image',image:'a'.repeat(32)});
  assert.throws(()=>validateEnvelope({config,images:{}}));
  assert.throws(()=>validateEnvelope({config,images:{['a'.repeat(32)]:'<svg>'}}));
  assert.equal(validateEnvelope({application:'368K Studio',config,images:{['a'.repeat(32)]:'YWJjZA=='}}).config.parts.wallpaper.enabled,true);
  assert.throws(()=>validateEnvelope({config,artist:{templateImages:{'/arbitrary.png':'YWJjZA=='}}}));
});
test('CRC32 and store-only ZIP have valid central directory and UTF-8 flag',async()=>{
  const enc=new TextEncoder();assert.equal(crc32(enc.encode('123456789')),0xcbf43926);
  const zip=new Uint8Array(await zipFiles([['png/test.png',new Uint8Array([1,2,3])],['note.txt','hello']]).arrayBuffer()),v=new DataView(zip.buffer);
  assert.equal(v.getUint32(0,true),0x04034b50);assert.equal(v.getUint16(6,true),0x800);assert.equal(v.getUint32(zip.length-22,true),0x06054b50);assert.equal(v.getUint16(zip.length-12,true),2);
  assert.throws(()=>zipFiles([['../bad','no']]));
});
