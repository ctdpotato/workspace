#!/usr/bin/env python3
"""Workspace server with persistent storage"""
import http.server
import json
import os
import threading
import re

PORT = 8889
HTML_PATH = '/app/data/所有对话/主对话/用户上传/daily_plan.html'
DATA_PATH = '/app/data/所有对话/主对话/用户上传/workspace_data.json'

# ---- Proxy code to inject after LS definition ----
PROXY_CODE = r'''
// ==== SERVER PERSISTENCE PROXY ====
(function(){
  var _store={};
  var _origLS=window.localStorage;
  
  // Proxy for localStorage
  var _proxy=new Proxy(_origLS,{
    get:function(target,prop){
      if(prop==='getItem')return function(k){
        try{return _store.hasOwnProperty(k)?_store[k]:null}catch(e){return null}
      };
      if(prop==='setItem')return function(k,v){
        _store[k]=String(v);_debouncedSave()
      };
      if(prop==='removeItem')return function(k){
        delete _store[k];_debouncedSave()
      };
      if(prop==='clear')return function(){
        _store={};_debouncedSave()
      };
      if(prop==='key')return function(i){return Object.keys(_store)[i]||null};
      if(prop==='length')return Object.keys(_store).length;
      var v=target[prop];
      return typeof v==='function'?v.bind(target):v;
    },
    set:function(target,prop,value){
      if(typeof prop==='string'&&prop!=='length'){
        _store[prop]=String(value);_debouncedSave()
      }
      return true;
    }
  });
  window.localStorage=_proxy;
  
  // Also patch the LS object
  LS.get=function(k,d){try{var v=_store.hasOwnProperty(k)?_store[k]:null;return v?JSON.parse(v):d}catch(e){return d}};
  LS.set=function(k,v){_store[k]=JSON.stringify(v);_debouncedSave()};
  
  // Debounced save to server
  var _saveTimer=null;
  function _debouncedSave(){
    if(_saveTimer)clearTimeout(_saveTimer);
    _saveTimer=setTimeout(function(){
      try{
        _origLS.setItem('__cache__',JSON.stringify(_store));
        fetch('/api/data',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(_store)}).catch(function(){})
      }catch(e){}
    },1000);
  }
  
  // Load from server on startup
  window.__dataReady=new Promise(function(resolve){
    fetch('/api/data').then(function(r){return r.json()}).then(function(data){
      if(data&&typeof data==='object'){
        for(var k in data){
          if(data.hasOwnProperty(k)){
            _store[k]=typeof data[k]==='string'?data[k]:JSON.stringify(data[k])
          }
        }
      }
      resolve()
    }).catch(function(){resolve()})
  });
})();
'''

# Deferred init code - replace the two standalone render calls
INIT_CODE = r'''
// ==== DEFERRED INIT (server persistence) ====
window.__dataReady.then(function(){
  try{checkDayReset()}catch(e){}
  renderTasks();
  if(typeof planState!=='undefined'&&typeof TOTAL_TASKS!=='undefined'&&planState.done.length===TOTAL_TASKS){try{showCelebration()}catch(e){}}
  renderTopics();
});
'''


def modify_html(html_content):
    """Inject proxy code and defer initial renders"""
    
    # 1. Find the LS definition and inject proxy after it
    ls_pattern = r"const LS=\{get:.*?\)\};"
    match = re.search(ls_pattern, html_content)
    if match:
        insert_pos = match.end()
        html_content = html_content[:insert_pos] + '\n' + PROXY_CODE + '\n' + html_content[insert_pos:]
        print(f"[OK] Injected proxy after LS definition at position {insert_pos}")
    else:
        print("[WARN] Could not find LS definition")
    
    # 2. Comment out standalone renderTasks() call
    html_content = re.sub(
        r"(if\(planState\.done\.length===TOTAL_TASKS\)showCelebration\(\);\n)renderTasks\(\);",
        r"\1//renderTasks();// deferred to server-init",
        html_content
    )
    print("[OK] Deferred renderTasks()")
    
    # 3. Comment out standalone renderTopics() call
    html_content = re.sub(
        r"(\}\n\n)renderTopics\(\);(\n\n// ======================== HELPERS)",
        r"\1//renderTopics();// deferred to server-init\2",
        html_content
    )
    print("[OK] Deferred renderTopics()")
    
    # 4. Add deferred init code before closing </script>
    html_content = html_content.replace('</script>', INIT_CODE + '\n</script>')
    print("[OK] Added deferred init code")
    
    return html_content


class WorkspaceHandler(http.server.BaseHTTPRequestHandler):
    data_lock = threading.Lock()
    modified_html = None
    
    def load_data(self):
        with self.data_lock:
            if os.path.exists(DATA_PATH):
                try:
                    with open(DATA_PATH, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    return {}
            return {}
    
    def save_data(self, data):
        with self.data_lock:
            with open(DATA_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
    
    def do_GET(self):
        if self.path == '/api/data':
            data = self.load_data()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        elif self.path == '/' or self.path == '/daily_plan.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.modified_html)
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/data':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                self.save_data(data)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Quiet


# Prepare modified HTML
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    original_html = f.read()

modified = modify_html(original_html)
WorkspaceHandler.modified_html = modified.encode('utf-8')

# Verify modifications
if b'SERVER PERSISTENCE PROXY' in WorkspaceHandler.modified_html:
    print("[OK] Proxy code present in served HTML")
else:
    print("[ERROR] Proxy code NOT found in served HTML!")

if b'DEFERRED INIT' in WorkspaceHandler.modified_html:
    print("[OK] Deferred init code present")
else:
    print("[ERROR] Deferred init code NOT found!")

server = http.server.HTTPServer(('0.0.0.0', PORT), WorkspaceHandler)
print(f"\nServer running on port {PORT}")
server.serve_forever()
