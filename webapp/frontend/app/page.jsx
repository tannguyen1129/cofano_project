"use client";
import { useEffect, useRef, useState, useMemo } from "react";
import {
  Fuel, Calendar, Database, Crosshair, Store, Layers, Gauge, TrendingDown, ShieldCheck,
  Droplets, LineChart, BarChart3, Grid3x3, Globe, Tags, Info, PieChart, ChevronDown, Check, LogOut,
} from "lucide-react";

function Dropdown({value,onChange,options,placeholder,minw=150}){
  const [open,setOpen]=useState(false); const ref=useRef();
  useEffect(()=>{ const h=e=>{ if(ref.current&&!ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown",h); return ()=>document.removeEventListener("mousedown",h); },[]);
  const sel=options.find(o=>o.value===value);
  return (<div className={"dd"+(open?" open":"")} ref={ref}>
    <button className="dd-btn" style={{minWidth:minw}} onClick={()=>setOpen(o=>!o)}>
      <span>{sel?sel.label:placeholder}</span><ChevronDown size={15}/></button>
    {open&&<div className="dd-menu">{options.map(o=>(
      <div key={o.value} className={"dd-opt"+(o.value===value?" on":"")} onClick={()=>{onChange(o.value);setOpen(false);}}>
        <span>{o.label}</span>{o.value===value&&<Check size={15}/>}</div>))}</div>}
  </div>);
}

const API = "/api";
const FUELC = { Euro95:"#0a9c4a", Diesel:"#2563eb", Super98:"#e8820c", AdBlue:"#7c4dff", LPG:"#e11d65" };
const T = {
 title:{vi:"Bảng điều khiển Dự báo Nhu cầu",en:"Demand Forecast Dashboard"},
 sub:{vi:"Dự báo nhu cầu nhiên liệu theo trạm, sản phẩm và ngày, kèm mức trữ an toàn cho kế hoạch giao hàng ROVER",
      en:"Daily fuel-demand forecasts per station and product, with safety-stock levels for the ROVER replenishment plan"},
 nav_ov:{vi:"Tổng quan",en:"Overview"}, nav_fc:{vi:"Dự báo",en:"Forecast"}, nav_op:{vi:"Vận hành",en:"Operations"}, nav_net:{vi:"Mạng trạm",en:"Network"}, nav_ref:{vi:"Tham chiếu",en:"Reference"},
 live:{vi:"Hệ thống đang hoạt động",en:"System online"},
 s_traj:{vi:"Nhu cầu dự báo theo thời gian",en:"Forecast demand over time"},
 d_traj:{vi:"Biểu đồ thể hiện nhu cầu nhiên liệu dự báo (đơn vị: lít). Đường xanh là dự báo trung vị P50 — lượng bán kỳ vọng. Vùng hồng phía trên là phân vị 95% (P95) — mức cần trữ để gần như không bao giờ thiếu hàng. Số liệu bán thực tế có đến 22/05/2026; mọi giá trị sau mốc này là dự báo của mô hình.",
         en:"Forecast fuel demand in litres. The green line is the median forecast (P50) — the expected sales volume. The pink band above is the 95th percentile (P95) — the stock level needed to almost never run short. Observed sales run through 22 May 2026; every value after that date is a model forecast."},
 lg_p50:{vi:"Dự báo P50 (lượng kỳ vọng)",en:"P50 forecast (expected)"}, lg_p95:{vi:"Mức an toàn P95 (cần trữ)",en:"P95 safety level (stock to)"}, lg_today:{vi:"Hôm nay",en:"Today"},
 g_day:{vi:"Theo ngày",en:"Daily"}, g_week:{vi:"Theo tuần",en:"Weekly"},
 all_st:{vi:"Tất cả trạm",en:"All stations"}, all_pr:{vi:"Tất cả sản phẩm",en:"All products"},
 gloss:{vi:"P50 = mức dự báo có 50% khả năng nhu cầu nằm dưới (giá trị trung vị, dùng để ước lượng lượng bán). P95 = mức có 95% khả năng nhu cầu nằm dưới — đổ tới mức này thì trung bình chỉ ~5% số ngày bị thiếu hàng. Khoảng cách P95−P50 chính là lượng trữ an toàn cần thêm.",
        en:"P50 = the level the demand falls below 50% of the time (the median; used to estimate sales). P95 = the level demand falls below 95% of the time — replenishing to it leaves only ~5% of days short on average. The gap P95−P50 is the safety stock to add."},
 s_op:{vi:"Tác động vận hành tới chi phí tồn kho",en:"Operational impact on inventory cost"},
 d_op:{vi:"“Levels penalty” là chi phí proxy khi mức tồn kho sai, gồm ba phần: thiếu hàng (trạm cạn, mất doanh thu), tồn dư hợp lệ (vẫn nằm trong sức chứa bồn), và phần không xả được (vượt sức chứa còn lại → phải đổi tuyến/lập lại kế hoạch). Ba chi phí bất đối xứng — thiếu hàng tốn nhất. Mô phỏng cho thấy dự báo P50 không giảm được chi phí; chỉ mức trữ an toàn P95 mới giảm.",
       en:"The “levels penalty” is a proxy cost for wrong inventory levels, in three parts: shortages (a dry station, lost sales), feasible carryover (stock that still fits in the tank), and undeliverable volume (beyond the remaining headroom → a reroute/replan). The three are asymmetric — a shortage costs most. The simulation shows the P50 forecast does not cut the cost; only the P95 safety level does."},
 n_op:{vi:"Giả định mô phỏng: mỗi lần giao bị chặn cứng bởi sức chứa bồn; sức chứa ước lượng = 1,3 × mức tiêu thụ 7 ngày liên tiếp cao nhất trong lịch sử trước kỳ kiểm tra; trọng số phạt thiếu/tồn dư/không-xả-được = 10/1/5. Cần sức chứa bồn và chi phí giao hàng thực tế để có con số chính xác.",
       en:"Simulation assumptions: every delivery is hard-capped at tank capacity; capacity is proxied as 1.3 × the heaviest complete 7-day volume before the test window; penalty weights shortfall/carryover/undeliverable = 10/1/5. Real tank capacities and delivery costs are needed for an exact figure."},
 sim_pick:{vi:"Xem mô phỏng tồn kho cho một bồn cụ thể:",en:"Inspect the simulated stock of one tank:"},
 sim_so:{vi:"Số ngày cạn hàng",en:"Stockout days"},
 s_hm:{vi:"Sản lượng theo Trạm × Sản phẩm",en:"Volume by station × product"},
 d_hm:{vi:"Sản lượng bán trung bình (lít/ngày) trong lịch sử. Màu càng đậm bán càng nhiều; ô trống là trạm không bán sản phẩm đó.",en:"Average historical sales (litres/day). Darker means higher volume; a blank cell means the station does not sell that product."},
 s_geo:{vi:"Bản đồ mạng trạm",en:"Station network map"},
 d_geo:{vi:"Vị trí 20 trạm (toạ độ đã làm tròn để ẩn danh); bán kính chấm tỉ lệ với tổng sản lượng. Mạng lưới nằm gọn trong một vùng sát biên giới.",en:"Location of the 20 stations (coordinates rounded for anonymity); marker radius scales with total volume. The network sits within a single cross-border area."},
 s_fuel:{vi:"Tỉ trọng theo loại nhiên liệu",en:"Volume share by fuel"},
 d_fuel:{vi:"Tỉ lệ sản lượng từng loại nhiên liệu trong kỳ dự báo. Euro95 và Diesel chiếm khoảng 93% — nơi sai số ảnh hưởng nhiều nhất tới kế hoạch.",en:"Each fuel's share of forecast volume. Euro95 and Diesel are ~93% — where errors matter most for planning."},
 s_map:{vi:"Ánh xạ sản phẩm và đối chiếu mô hình",en:"Product mapping and model benchmark"},
 d_map:{vi:"P1–P5 tương ứng loại nhiên liệu nào, kèm so sánh sai số (WAPE) giữa mô hình và quy tắc “lặp lại tuần trước”.",en:"Which fuel each of P1–P5 denotes, with the error (WAPE) of the model versus the “repeat last week” rule."},
 footer:{vi:"Cofano · Hệ thống dự báo nhu cầu nhiên liệu cho ROVER · 20 trạm, 69 tổ hợp trạm–sản phẩm được dự báo độc lập · dữ liệu lịch sử 01/2024 – 05/2026",
         en:"Cofano · Fuel-demand forecasting for ROVER · 20 stations, 69 station–product combinations forecast independently · historical data 01/2024 – 05/2026"},
};
const KICON={wape_main:Gauge,vs_naive:TrendingDown,penalty_cut:ShieldCheck,stockout_cut:Droplets};
const KCLASS={wape_main:"g",vs_naive:"b",penalty_cut:"g",stockout_cut:"r"};
const weekStart=ds=>{const d=new Date(ds+"T00:00:00");const k=(d.getDay()+6)%7;d.setDate(d.getDate()-k);return d.toISOString().slice(0,10);};

export default function Page(){
  const [d,setD]=useState(null), [lang,setLang]=useState("vi"), [active,setActive]=useState("ov");
  const [fcSt,setFcSt]=useState(""), [fcPr,setFcPr]=useState(""), [gran,setGran]=useState("day"), [recs,setRecs]=useState([]);
  const [rngFrom,setRngFrom]=useState(""), [rngTo,setRngTo]=useState("");
  const [simSt,setSimSt]=useState(""), [simPr,setSimPr]=useState(""), [sim,setSim]=useState(null);
  const C1=useRef(),C2=useRef(),C3=useRef(),C4=useRef(),mapRef=useRef();
  const ch=useRef({}), mapObj=useRef(null);
  const tr=k=>T[k][lang];
  const fmt=n=>Number(n).toLocaleString(lang==="vi"?"vi-VN":"en-US");

  useEffect(()=>{ fetch(`${API}/dashboard`).then(r=>r.json()).then(x=>{setD(x);setSim(x.sim);setSimSt(x.sim.station);setSimPr(x.sim.product);
    setRngFrom(x.dates[0]);setRngTo(x.dates[x.dates.length-1]);}); },[]);
  useEffect(()=>{ const q=new URLSearchParams(); if(fcSt)q.set("station",fcSt); if(fcPr)q.set("product",fcPr);
    fetch(`${API}/forecast?${q}`).then(r=>r.json()).then(setRecs); },[fcSt,fcPr]);
  useEffect(()=>{ if(!simSt||!simPr) return; const q=new URLSearchParams({station:simSt,product:simPr});
    fetch(`${API}/sim?${q}`).then(r=>r.json()).then(setSim); },[simSt,simPr]);

  const agg=useMemo(()=>{
    if(!recs.length) return {labels:[],p50:[],p95:[],actual:[]};
    const m={}; recs.forEach(r=>{const k=gran==="week"?weekStart(r.date):r.date;
      (m[k]=m[k]||{p50:null,p95:null,actual:null});
      if(r.p50!=null){m[k].p50=(m[k].p50||0)+r.p50;} if(r.p95!=null){m[k].p95=(m[k].p95||0)+r.p95;}
      if(r.actual!=null){m[k].actual=(m[k].actual||0)+r.actual;}});
    const labels=Object.keys(m).sort();
    const R=v=>v==null?null:Math.round(v);
    return {labels,p50:labels.map(k=>R(m[k].p50)),p95:labels.map(k=>R(m[k].p95)),actual:labels.map(k=>R(m[k].actual))};
  },[recs,gran]);

  const view=useMemo(()=>{
    if(!agg.labels.length||!rngFrom||!rngTo) return agg;
    const ix=agg.labels.map((_,i)=>i).filter(i=>agg.labels[i]>=rngFrom&&agg.labels[i]<=rngTo);
    return {labels:ix.map(i=>agg.labels[i]),p50:ix.map(i=>agg.p50[i]),p95:ix.map(i=>agg.p95[i]),actual:ix.map(i=>agg.actual[i])};
  },[agg,rngFrom,rngTo]);

  // forecast chart
  useEffect(()=>{
    if(!window.Chart||!C1.current||!view.labels.length) return;
    const Ch=window.Chart; Ch.defaults.font.family="Inter, system-ui, sans-serif"; Ch.defaults.color="#7c8aa0";
    Object.assign(Ch.defaults.plugins.tooltip,{backgroundColor:"#ffffff",titleColor:"#0f2230",bodyColor:"#384759",
      borderColor:"#e6ebf2",borderWidth:1,cornerRadius:11,padding:11,boxPadding:5,titleFont:{weight:"700"},
      usePointStyle:true,bodySpacing:5,caretSize:6});
    ch.current.fc&&ch.current.fc.destroy();
    const today=d?.meta.today, ti=gran==="day"?view.labels.indexOf(today):-1, grid="#eef2f7";
    const actLabel=lang==="vi"?"Thực tế":"Actual";
    ch.current.fc=new Ch(C1.current,{type:"line",data:{labels:view.labels,datasets:[
      {label:"P95",data:view.p95,borderColor:"#e11d65",backgroundColor:"rgba(225,29,101,.06)",fill:true,borderWidth:1.4,pointRadius:0,tension:.3,spanGaps:false},
      {label:"P50",data:view.p50,borderColor:"#0a9c4a",backgroundColor:"rgba(10,156,74,.10)",fill:true,borderWidth:2.4,pointRadius:0,tension:.3,spanGaps:false},
      {label:actLabel,data:view.actual,borderColor:"#334155",backgroundColor:"rgba(51,65,85,.05)",borderWidth:1.8,pointRadius:0,tension:.3,spanGaps:false,borderDash:[]},
      {label:"today",data:view.labels.map((x,i)=>i===ti?(view.actual[i]??view.p50[i]):null),borderColor:"#2563eb",pointBackgroundColor:"#2563eb",pointBorderColor:"#fff",pointBorderWidth:2,pointRadius:6,showLine:false}]},
      options:{maintainAspectRatio:false,interaction:{mode:"index",intersect:false},plugins:{legend:{display:false},
        tooltip:{callbacks:{title:c=>c[0].label,label:c=>(c.dataset.label==="today"?"":c.dataset.label+": "+fmt(Math.round(c.parsed.y))+" L")}}},
        scales:{x:{ticks:{maxTicksLimit:gran==="week"?12:10,font:{size:10}},grid:{display:false}},y:{ticks:{callback:v=>fmt(v),font:{size:10}},grid:{color:grid},border:{display:false},title:{display:true,text:gran==="week"?"L / "+(lang==="vi"?"tuần":"week"):"L / "+(lang==="vi"?"ngày":"day"),font:{size:10}}}}}});
    return ()=>ch.current.fc&&ch.current.fc.destroy();
  },[view,lang,d,gran]);

  // fuel doughnut
  useEffect(()=>{ if(!window.Chart||!C2.current||!d) return;
    ch.current.fuel&&ch.current.fuel.destroy();
    ch.current.fuel=new window.Chart(C2.current,{type:"doughnut",data:{labels:d.fuel_totals.map(f=>f.fuel),
      datasets:[{data:d.fuel_totals.map(f=>f.liters),backgroundColor:d.fuel_totals.map(f=>FUELC[f.fuel]),borderWidth:3,borderColor:"#fff",hoverOffset:6}]},
      options:{maintainAspectRatio:false,cutout:"62%",plugins:{legend:{position:"right",labels:{font:{size:12.5},boxWidth:10,usePointStyle:true,pointStyle:"circle",padding:12}},tooltip:{callbacks:{label:c=>c.label+": "+fmt(c.parsed)+" L"}}}}});
    return ()=>ch.current.fuel&&ch.current.fuel.destroy();
  },[d,lang]);

  // penalty bars
  useEffect(()=>{ if(!window.Chart||!C3.current||!d) return;
    ch.current.pen&&ch.current.pen.destroy(); const p=d.penalty,grid="#eef2f7";
    ch.current.pen=new window.Chart(C3.current,{type:"bar",data:{labels:p.map(x=>({naive:"Naive",model_p50:"Model P50",model_p95:"Model P95"}[x.policy]||x.policy)),
      datasets:[{label:lang==="vi"?"Ngày cạn hàng":"Stockout days",data:p.map(x=>x.stockout_days),backgroundColor:"#e11d65",borderRadius:6,yAxisID:"y",maxBarThickness:36},
                {label:lang==="vi"?"Chi phí phạt (triệu)":"Penalty (M)",data:p.map(x=>x.penalty/1e6),backgroundColor:"#2563eb",borderRadius:6,yAxisID:"y1",maxBarThickness:36}]},
      options:{maintainAspectRatio:false,plugins:{legend:{labels:{font:{size:11.5},boxWidth:10,usePointStyle:true,pointStyle:"circle"}}},scales:{
        y:{position:"left",title:{display:true,text:lang==="vi"?"Ngày cạn":"Dry days",font:{size:10}},grid:{color:grid},border:{display:false},ticks:{font:{size:10}}},
        y1:{position:"right",title:{display:true,text:lang==="vi"?"Phạt (triệu)":"Penalty (M)",font:{size:10}},grid:{drawOnChartArea:false},border:{display:false},ticks:{font:{size:10}}},x:{grid:{display:false},ticks:{font:{size:11}}}}}});
    return ()=>ch.current.pen&&ch.current.pen.destroy();
  },[d,lang]);

  // inventory sim
  useEffect(()=>{ if(!window.Chart||!C4.current||!sim) return;
    ch.current.sim&&ch.current.sim.destroy(); const grid="#eef2f7";
    ch.current.sim=new window.Chart(C4.current,{type:"line",data:{labels:sim.dates,datasets:[
      {label:"Naive",data:sim.naive,borderColor:"#c2ccd8",borderWidth:1.4,pointRadius:0,tension:.25},
      {label:"P50",data:sim.p50,borderColor:"#2563eb",borderWidth:1.4,pointRadius:0,tension:.25},
      {label:"P95",data:sim.p95,borderColor:"#0a9c4a",borderWidth:2.2,pointRadius:0,tension:.25}]},
      options:{maintainAspectRatio:false,plugins:{legend:{labels:{font:{size:11.5},boxWidth:10,usePointStyle:true,pointStyle:"circle"}},
        tooltip:{callbacks:{label:c=>c.dataset.label+": "+fmt(Math.round(c.parsed.y))+" L"}}},
        scales:{x:{ticks:{maxTicksLimit:6,font:{size:9}},grid:{display:false}},y:{ticks:{callback:v=>fmt(v),font:{size:9}},grid:{color:grid},border:{display:false},min:0,title:{display:true,text:lang==="vi"?"Tồn kho (L) — chạm 0 là cạn":"Stock (L) — 0 = stockout",font:{size:10}}}}}});
    return ()=>ch.current.sim&&ch.current.sim.destroy();
  },[sim,lang]);

  // Leaflet map (Europe)
  useEffect(()=>{ if(!window.L||!mapRef.current||!d) return;
    if(mapObj.current){mapObj.current.remove();mapObj.current=null;}
    const L=window.L, map=L.map(mapRef.current,{scrollWheelZoom:false,attributionControl:false}).setView([51.1,4.4],8);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",{maxZoom:12,subdomains:"abcd"}).addTo(map);
    const mx=Math.max(...d.geo.map(g=>g.d));
    d.geo.forEach(g=>{const col=g.brand==="Brand B"?"#2563eb":"#e11d44";
      const html=`<div class="pp-name">${g.s}<span class="pp-brand" style="background:${col}1f;color:${col}">${g.brand}</span></div>`+
        `<div class="pp-val">${fmt(Math.round(g.d))} L · ${lang==="vi"?"tổng sản lượng lịch sử":"total historical volume"}</div>`;
      L.circleMarker([g.lat,g.lon],{radius:6+18*Math.sqrt(g.d/mx),color:col,weight:1.4,fillColor:col,fillOpacity:.45})
        .addTo(map).bindPopup(html,{closeButton:true,maxWidth:240});});
    mapObj.current=map; setTimeout(()=>map.invalidateSize(),200);
    return ()=>{map.remove();mapObj.current=null;};
  },[d]);

  if(!d) return <div className="loading"><div className="spin"></div>Loading…</div>;
  const kp=d.kpis.reduce((a,k)=>(a[k.key]=k,a),{}); const order=["wape_main","vs_naive","penalty_cut","stockout_cut"];
  const stations=[...new Set(d.geo.map(g=>g.s))].sort();
  const products=[...d.product_map].map(p=>({code:p.code,fuel:p.fuel})).sort((a,b)=>a.code.localeCompare(b.code));
  const hv=d.station_product.values.flat().filter(v=>v!=null); const lo=Math.log(Math.min(...hv)),hi=Math.log(Math.max(...hv));
  const heat=v=>{ if(v==null)return"#f3f6fa"; const t=(Math.log(v)-lo)/(hi-lo); return `rgb(${Math.round(255-25*t)},${Math.round(244-150*t)},${Math.round(230-170*t)})`; };
  const NAV=[["ov",T.nav_ov,Gauge],["fc",T.nav_fc,LineChart],["op",T.nav_op,BarChart3],["net",T.nav_net,Globe],["ref",T.nav_ref,Tags]];
  const SecH=({Icon,title})=>(<div className="sec-h"><span className="ic"><Icon size={17}/></span><h2>{title}</h2></div>);
  const so=sim?.stockout||{};

  return (<div className="app">
    <aside className="sidebar">
      <div className="sb-logo"><span className="mark"><Fuel size={20}/></span>
        <div><b>Fuel Forecast</b><span>Cofano · ROVER</span></div></div>
      <nav className="sb-nav">{NAV.map(([id,lbl,Icon])=>(
        <a key={id} className={active===id?"active":""} onClick={()=>{setActive(id);document.getElementById(id)?.scrollIntoView({behavior:"smooth"});}}>
          <Icon size={17}/>{lbl[lang]}</a>))}</nav>
      <div className="sb-foot">
        <div className="sb-status"><span className="dot"></span>{tr("live")}</div>
        <div className="toggle"><button className={lang==="vi"?"on":""} onClick={()=>setLang("vi")}>VI</button>
          <button className={lang==="en"?"on":""} onClick={()=>setLang("en")}>EN</button></div>
      </div>
    </aside>

    <div className="content">
      <div className="topbar">
        <h1>{tr("title")}</h1><div className="sub">{tr("sub")}</div>
        <div className="chips">
          <span className="chip"><Calendar size={14}/>{lang==="vi"?"Hôm nay":"Today"}: <b>{d.meta.server_now||d.meta.today}</b></span>
          <span className="chip ok" title={lang==="vi"?"Dữ liệu cập nhật tới":"Data updated through"}>
            <Database size={14}/>{lang==="vi"?"Cập nhật":"Updated"}: <b>{d.meta.data_as_of||d.meta.last_actual}</b>
            <span className="statusdot"/>Live
          </span>
          <span className="chip"><Crosshair size={14}/>{lang==="vi"?"Tuần kế hoạch":"Planning week"}: <b>{d.meta.start} → {d.meta.end}</b></span>
          <span className="chip"><Store size={14}/><b>{(d.meta.brands||[]).map(b=>`${b.n} ${b.brand}`).join(" + ")}</b></span>
          <span className="chip"><Layers size={14}/>{lang==="vi"?"Tổ hợp trạm–sản phẩm":"Station–product pairs"}: <b>{d.meta.n_series}</b></span>
          <a className="chip logout" href="/logout" title={lang==="vi"?"Đăng xuất":"Sign out"}><LogOut size={14}/>{lang==="vi"?"Đăng xuất":"Sign out"}</a>
        </div>
      </div>

      <main className="main">
        <div id="ov" className="kpis">{order.map(k=>{const Icon=KICON[k];return(
          <div className={"kpi "+KCLASS[k]} key={k}><div className="ic"><Icon size={20}/></div>
            <div className="v">{(k==="wape_main"?"":"−")+kp[k].value}%</div>
            <div className="l">{lang==="vi"?kp[k].label_vi:kp[k].label_en}</div></div>);})}</div>

        <section id="fc">
          <SecH Icon={LineChart} title={tr("s_traj")}/>
          <p className="desc">{tr("d_traj")}</p>
          <div className="controls" style={{paddingLeft:43}}>
            <Dropdown value={fcSt} onChange={setFcSt} placeholder={tr("all_st")} minw={150}
              options={[{value:"",label:tr("all_st")},...stations.map(s=>({value:s,label:s}))]}/>
            <Dropdown value={fcPr} onChange={setFcPr} placeholder={tr("all_pr")} minw={172}
              options={[{value:"",label:tr("all_pr")},...products.map(p=>({value:p.code,label:`${p.code} · ${p.fuel}`}))]}/>
            <div className="seg"><button className={gran==="day"?"on":""} onClick={()=>setGran("day")}>{tr("g_day")}</button>
              <button className={gran==="week"?"on":""} onClick={()=>setGran("week")}>{tr("g_week")}</button></div>
          </div>
          <div className="controls" style={{paddingLeft:43}}>
            <span className="range"><Calendar size={14}/>{lang==="vi"?"Khoảng thời gian":"Date range"}</span>
            <input type="date" value={rngFrom} min={agg.labels[0]} max={rngTo||agg.labels[agg.labels.length-1]} onChange={e=>setRngFrom(e.target.value)}/>
            <span className="range">→</span>
            <input type="date" value={rngTo} min={rngFrom||agg.labels[0]} max={agg.labels[agg.labels.length-1]} onChange={e=>setRngTo(e.target.value)}/>
            <button className="preset" onClick={()=>{setRngFrom(d.dates[0]);setRngTo(d.dates[d.dates.length-1]);}}>{lang==="vi"?"Tuần dự báo":"Forecast wk"}</button>
            <button className="preset" onClick={()=>{const L=agg.labels;setRngFrom(L[Math.max(0,L.length-30)]);setRngTo(L[L.length-1]);}}>{lang==="vi"?"1 tháng":"1 month"}</button>
            <button className="preset" onClick={()=>{setRngFrom(agg.labels[0]);setRngTo(agg.labels[agg.labels.length-1]);}}>{lang==="vi"?"Cả kỳ":"Full"}</button>
          </div>
          <div className="chartbox"><canvas ref={C1}></canvas></div>
          <div className="legend">
            <span><span className="sw" style={{background:"#334155"}}></span>{lang==="vi"?"Thực tế (lịch sử)":"Actual (history)"}</span>
            <span><span className="sw" style={{background:"#0a9c4a"}}></span>{tr("lg_p50")}</span>
            <span><span className="sw" style={{background:"#e11d65"}}></span>{tr("lg_p95")}</span>
            <span><span className="sw" style={{background:"#2563eb",width:10,height:10,borderRadius:"50%"}}></span>{tr("lg_today")}</span></div>
          <div className="gloss"><Info size={15}/><span>{tr("gloss")}</span></div>
        </section>

        <section id="op">
          <SecH Icon={BarChart3} title={tr("s_op")}/>
          <p className="desc">{tr("d_op")}</p>
          <div className="grid2b">
            <div className="chartbox sm"><canvas ref={C3}></canvas></div>
            <div>
              <div className="controls" style={{justifyContent:"flex-end"}}>
                <span className="ctl-lab">{tr("sim_pick")}</span>
                <Dropdown value={simSt} onChange={setSimSt} minw={92} options={stations.map(s=>({value:s,label:s}))}/>
                <Dropdown value={simPr} onChange={setSimPr} minw={150} options={products.map(p=>({value:p.code,label:`${p.code} · ${p.fuel}`}))}/>
              </div>
              <div className="chartbox" style={{height:248}}><canvas ref={C4}></canvas></div>
              <div className="solist">{["naive","p50","p95"].map(k=>(
                <span key={k} className={"so "+(k==="p95"?"good":"")}>{({naive:"Naive",p50:"P50",p95:"P95"})[k]}: <b>{so[k]??"–"}</b> {tr("sim_so").toLowerCase()}</span>))}</div>
            </div>
          </div>
          <div className="note"><Info size={14}/>{tr("n_op")}</div>
        </section>

        <div id="net" className="grid2b">
          <section>
            <SecH Icon={Grid3x3} title={tr("s_hm")}/>
            <p className="desc">{tr("d_hm")}</p>
            <div className="scroll" style={{maxHeight:440}}><table className="hm"><thead><tr><th></th>
              {d.station_product.products.map(p=><th key={p}>{p}</th>)}</tr></thead><tbody>
              {d.station_product.stations.map((s,i)=>(<tr key={s}><td className="lab">{s}</td>
                {d.station_product.values[i].map((v,j)=><td key={j} style={{background:heat(v),color:v&&(Math.log(v)-lo)/(hi-lo)>.62?"#fff":"#1f2d3b"}}>{v==null?"":fmt(v)}</td>)}</tr>))}
            </tbody></table></div>
          </section>
          <section>
            <SecH Icon={Globe} title={tr("s_geo")}/>
            <p className="desc">{tr("d_geo")}</p>
            <div ref={mapRef} className="mapbox"></div>
          </section>
        </div>

        <div id="ref" className="grid2b">
          <section>
            <SecH Icon={Tags} title={tr("s_map")}/>
            <p className="desc">{tr("d_map")}</p>
            <table><thead><tr>
              <th>{lang==="vi"?"Sản phẩm":"Product"}</th><th>{lang==="vi"?"Nhiên liệu":"Fuel"}</th><th>% {lang==="vi"?"sản lượng":"volume"}</th></tr></thead>
              <tbody>{d.product_map.map(p=>(<tr key={p.code}><td>{p.code}</td><td>{p.fuel}</td><td>{p.volume_share}%</td></tr>))}
              <tr><td colSpan={3} style={{paddingTop:14,color:"var(--mut)",fontSize:12}}>{lang==="vi"?"Đối chiếu sai số WAPE (thấp hơn là tốt hơn)":"WAPE error benchmark (lower is better)"}</td></tr>
              {d.benchmark.map((b,i)=>(<tr key={i}><td colSpan={2}>{b.model_name}</td><td>{b.wape}%{b.wape_main?` · ${lang==="vi"?"nhiên liệu chính":"main fuels"} ${b.wape_main}%`:""}</td></tr>))}
            </tbody></table>
          </section>
          <section>
            <SecH Icon={PieChart} title={tr("s_fuel")}/>
            <p className="desc">{tr("d_fuel")}</p>
            <div className="chartbox sm"><canvas ref={C2}></canvas></div>
          </section>
        </div>
      </main>
      <footer>
        {tr("footer")}
        {d?.meta?.real_cutoff &&
          <div className="finenote">{lang==="vi"
            ? `Bản demo: số liệu sau ${d.meta.real_cutoff} là ước lượng theo mùa vụ để giữ dashboard hiện thời.`
            : `Demo: figures after ${d.meta.real_cutoff} are seasonal estimates to keep the dashboard current.`}</div>}
      </footer>
    </div>
  </div>);
}
