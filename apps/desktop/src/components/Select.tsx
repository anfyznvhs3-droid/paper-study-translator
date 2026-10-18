import { forwardRef, useEffect, useId, useImperativeHandle, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";

interface SelectProps {
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  id?: string;
  describedBy?: string;
}

/** Shared select: selection commits on click/Enter, Escape leaves the value intact. */
export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select({label,value,options,onChange,disabled,id,describedBy}, ref) {
  const generatedId = useId();
  const listId = `${id ?? generatedId}-options`;
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const search = useRef({text:"",time:0});
  const [open,setOpen] = useState(false);
  const [active,setActive] = useState(0);
  const [position,setPosition] = useState<CSSProperties>({});
  const selected = options.findIndex(option => option.value === value);
  const isOpen = open && !disabled && options.length > 0;
  useImperativeHandle(ref, () => trigger.current!, []);

  function show(index = Math.max(0,selected)) { setActive(index);setOpen(true); }
  function choose(index: number) {
    const option = options[index];
    if (!option || disabled) return;
    onChange(option.value);setOpen(false);trigger.current?.focus();
  }
  useEffect(() => { if(disabled) setOpen(false); }, [disabled]);
  useEffect(() => { setActive(index => Math.min(index,Math.max(0,options.length-1))); }, [options.length]);
  useLayoutEffect(() => {
    if(!isOpen) return;
    function place() {
      const rect = trigger.current!.getBoundingClientRect();
      const below = innerHeight - rect.bottom - 12;
      const above = rect.top - 12;
      const upward = below < Math.min(256,options.length * 44 + 8) && above > below;
      const width = Math.min(rect.width,innerWidth - 24);
      setPosition({position:"fixed",left:Math.max(12,Math.min(rect.left,innerWidth-width-12)),width,
        top:upward?undefined:rect.bottom+6,bottom:upward?innerHeight-rect.top+6:undefined,
        maxHeight:Math.max(44,Math.min(256,upward?above:below))});
    }
    function outside(event: PointerEvent) {
      if(!trigger.current?.contains(event.target as Node) && !list.current?.contains(event.target as Node)) setOpen(false);
    }
    place();
    window.addEventListener("resize",place);
    window.addEventListener("scroll",place,true);
    document.addEventListener("pointerdown",outside);
    return () => {window.removeEventListener("resize",place);window.removeEventListener("scroll",place,true);document.removeEventListener("pointerdown",outside);};
  },[isOpen,options.length]);
  useEffect(() => {
    if(isOpen) list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({block:"nearest"});
  },[active,isOpen]);
  function handleKey(event: KeyboardEvent<HTMLButtonElement>) {
    if(disabled || !options.length) return;
    const count = options.length;
    if(["ArrowDown","ArrowUp","Home","End"].includes(event.key)) {
      event.preventDefault();
      const next = event.key==="Home"?0:event.key==="End"?count-1:!isOpen?Math.max(0,selected):(active+(event.key==="ArrowDown"?1:-1)+count)%count;
      show(next);
    } else if(event.key==="Enter" || event.key===" ") {
      event.preventDefault();isOpen?choose(active):show();
    } else if(event.key==="Escape" && isOpen) {
      event.preventDefault();event.stopPropagation();setOpen(false);
    } else if(event.key==="Tab") { setOpen(false); }
    else if(event.key.length===1 && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault();
      const now=Date.now();
      search.current={text:(now-search.current.time<600?search.current.text:"")+event.key.toLocaleLowerCase(),time:now};
      const match=options.findIndex(option=>option.label.toLocaleLowerCase().startsWith(search.current.text));
      if(match>=0)show(match);
    }
  }
  const portalRoot = trigger.current?.closest("dialog,.app-shell") ?? document.body;
  return <span className="qdt-select">
    <button type="button" id={id} ref={trigger} className="qdt-select-trigger" role="combobox" aria-label={label} data-value={value}
      aria-describedby={describedBy} aria-controls={isOpen?listId:undefined} aria-expanded={isOpen} aria-haspopup="listbox"
      aria-activedescendant={isOpen?`${listId}-${active}`:undefined} disabled={disabled || !options.length}
      onClick={() => isOpen?setOpen(false):show()} onKeyDown={handleKey} onBlur={() => setOpen(false)}>
      <span className="qdt-select-value">{options[selected]?.label ?? value}</span><Icon name="chevron" className="disclosure-icon" />
    </button>
    {isOpen && createPortal(<div ref={list} id={listId} className="qdt-select-menu" role="listbox" aria-label={label} style={position}>
      {options.map((option,index)=><div role="option" id={`${listId}-${index}`} key={option.value} aria-selected={value===option.value}
        data-value={option.value} data-index={index} className={`qdt-select-option${index===active?" is-active":""}`}
        onPointerDown={event=>event.preventDefault()} onPointerMove={()=>setActive(index)} onClick={()=>choose(index)}>
        <span>{option.label}</span>{value===option.value?<Icon name="check" />:null}
      </div>)}
    </div>,portalRoot)}
  </span>;
});
