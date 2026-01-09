import calendar
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk


DATA_FILE = Path(__file__).with_name("trade_journal_data.json")

def _parse_pl(raw: str) -> float:
    value = raw.strip().replace(",", ".")
    if value == "":
        raise ValueError("Valor vazio")
    return float(value)


def _date_key(d: date) -> str:
    return d.isoformat()


def _safe_write_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


class TradeJournalApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Trade Journal")
        self.minsize(1100, 700)

        today = date.today()
        self.current_year = today.year
        self.current_month = today.month
        self.selected_date = today

        # Dados estruturados:
        # self.data["trades"] = { "YYYY-MM-DD": [ ... ] }
        # self.data["accounts"] = [ "Conta Real", "Simulador", ... ]
        self.data: Dict[str, Any] = self._load_data()
        
        # Garantir estrutura mínima
        if "trades" not in self.data:
            self.data["trades"] = {}
        if "accounts" not in self.data:
            self.data["accounts"] = ["Padrão"]

        self._build_ui()
        self._build_menu()
        self._render_calendar()
        self._refresh_day_panel()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # Menu Arquivo
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Sair", command=self.quit)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        # Menu Cadastros
        cadastros_menu = tk.Menu(menubar, tearoff=0)
        cadastros_menu.add_command(label="Contas", command=self._manage_accounts)
        menubar.add_cascade(label="Cadastros", menu=cadastros_menu)

    def _load_data(self) -> Dict[str, Any]:
        if not DATA_FILE.exists():
            return {"trades": {}, "accounts": ["Padrão"]}
        try:
            payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                # Migração de versão anterior onde raiz era trades
                if "trades" in payload and isinstance(payload["trades"], dict):
                    # Já está no formato novo ou parecido
                    pass
                else:
                    # Formato antigo: payload é o dicionário de trades
                    # Vamos verificar se parece ser o dicionário de trades
                    # (chaves são datas, valores listas)
                    is_old = True
                    for k, v in payload.items():
                         if not isinstance(v, list):
                             is_old = False
                             break
                    if is_old:
                         payload = {"trades": payload, "accounts": ["Padrão"]}
                
                return payload
        except Exception:
            pass
        return {"trades": {}, "accounts": ["Padrão"]}

    def _save_data(self) -> None:
        _safe_write_json(DATA_FILE, self.data)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        calendar_frame = ttk.Frame(self, padding=12)
        calendar_frame.grid(row=0, column=0, sticky="nsew")
        calendar_frame.columnconfigure(0, weight=1)
        calendar_frame.rowconfigure(2, weight=1)

        header = ttk.Frame(calendar_frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)

        ttk.Button(header, text="◀", width=4, command=self._prev_month).grid(row=0, column=0, sticky="w")
        self.month_label = ttk.Label(header, text="", anchor="center", font=("Segoe UI", 16, "bold"))
        self.month_label.grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Button(header, text="▶", width=4, command=self._next_month).grid(row=0, column=2, sticky="e")

        weekdays = ttk.Frame(calendar_frame)
        weekdays.grid(row=1, column=0, sticky="ew", pady=(10, 4))
        for i, name in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
            weekdays.columnconfigure(i, weight=1, uniform="wd")
            ttk.Label(weekdays, text=name, anchor="center", font=("Segoe UI", 9, "bold")).grid(row=0, column=i, sticky="ew")

        self.days_grid = ttk.Frame(calendar_frame)
        self.days_grid.grid(row=2, column=0, sticky="nsew")
        for r in range(6):
            self.days_grid.rowconfigure(r, weight=1, uniform="row")
        for c in range(7):
            self.days_grid.columnconfigure(c, weight=1, uniform="col")

        self.day_buttons: List[tk.Button] = []
        for r in range(6):
            for c in range(7):
                # Usando tk.Button para poder alterar bg color
                btn = tk.Button(
                    self.days_grid,
                    text="",
                    command=lambda: None,
                    relief="flat"
                )
                btn.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
                self.day_buttons.append(btn)

        side_frame = ttk.Frame(self, padding=12)
        side_frame.grid(row=0, column=1, sticky="nsew")
        side_frame.columnconfigure(0, weight=1)
        side_frame.rowconfigure(3, weight=1)

        # Header do painel lateral
        side_header = ttk.Frame(side_frame)
        side_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.selected_label = ttk.Label(side_header, text="", font=("Segoe UI", 18, "bold"))
        self.selected_label.pack(side="left")

        self.day_total_label = ttk.Label(side_frame, text="", font=("Segoe UI", 12))
        self.day_total_label.grid(row=1, column=0, sticky="w", pady=(0, 10))

        # Filtros
        filters_frame = ttk.LabelFrame(side_frame, text="Filtros", padding=10)
        filters_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(filters_frame, text="Ativo:").pack(side="left", padx=(0, 5))
        self.filter_asset_var = tk.StringVar(value="Todos")
        self.filter_asset_cb = ttk.Combobox(filters_frame, textvariable=self.filter_asset_var, width=10, state="readonly")
        self.filter_asset_cb.pack(side="left", padx=(0, 10))
        self.filter_asset_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_day_panel())

        ttk.Label(filters_frame, text="Tipo:").pack(side="left", padx=(0, 5))
        self.filter_side_var = tk.StringVar(value="Todos")
        self.filter_side_cb = ttk.Combobox(filters_frame, textvariable=self.filter_side_var, values=["Todos", "Compra", "Venda"], width=8, state="readonly")
        self.filter_side_cb.pack(side="left", padx=(0, 10))
        self.filter_side_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_day_panel())

        ttk.Label(filters_frame, text="Conta:").pack(side="left", padx=(0, 5))
        self.filter_account_var = tk.StringVar(value="Todas")
        self.filter_account_cb = ttk.Combobox(filters_frame, textvariable=self.filter_account_var, width=12, state="readonly")
        self.filter_account_cb.pack(side="left")
        self.filter_account_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_day_panel())


        # Tabela
        self.trades_tree = ttk.Treeview(side_frame, columns=("side", "asset", "pl", "obs", "account"), show="headings", height=10)
        self.trades_tree.heading("side", text="Op")
        self.trades_tree.heading("asset", text="Ativo")
        self.trades_tree.heading("pl", text="L/P")
        self.trades_tree.heading("obs", text="Obs")
        self.trades_tree.heading("account", text="Conta")
        
        self.trades_tree.column("side", width=60, anchor="center")
        self.trades_tree.column("asset", width=80, anchor="w")
        self.trades_tree.column("pl", width=80, anchor="e")
        self.trades_tree.column("obs", width=120, anchor="w")
        self.trades_tree.column("account", width=100, anchor="w")
        
        self.trades_tree.grid(row=3, column=0, sticky="nsew")

        tree_scroll = ttk.Scrollbar(side_frame, orient="vertical", command=self.trades_tree.yview)
        self.trades_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=3, column=1, sticky="ns")

        # Formulário de Adição
        form = ttk.LabelFrame(side_frame, text="Nova Operação", padding=10)
        form.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # Linha 1: Conta e Tipo
        ttk.Label(form, text="Conta").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.account_var = tk.StringVar()
        self.account_cb = ttk.Combobox(form, textvariable=self.account_var, state="readonly")
        self.account_cb.grid(row=0, column=1, sticky="ew", padx=(0,10))
        
        # Botão para gerenciar contas
        ttk.Button(form, text="+", width=2, command=self._manage_accounts).grid(row=0, column=2, padx=(0, 10))

        ttk.Label(form, text="Tipo").grid(row=0, column=3, sticky="w", padx=(0,5))
        self.side_var = tk.StringVar(value="Compra")
        ttk.OptionMenu(form, self.side_var, "Compra", "Compra", "Venda").grid(row=0, column=4, sticky="ew")

        # Linha 2: Ativo e Valor
        ttk.Label(form, text="Ativo").grid(row=1, column=0, sticky="w", pady=(10,0))
        self.asset_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.asset_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(10,0), padx=(0,10))

        ttk.Label(form, text="L/P").grid(row=1, column=3, sticky="w", pady=(10,0))
        self.pl_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.pl_var).grid(row=1, column=4, sticky="ew", pady=(10,0))

        # Linha 3: Obs
        ttk.Label(form, text="Obs").grid(row=2, column=0, sticky="w", pady=(10,0))
        self.obs_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.obs_var).grid(row=2, column=1, columnspan=4, sticky="ew", pady=(10,0))

        # Botões
        actions = ttk.Frame(form)
        actions.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(15, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        
        # Usando tk.Button para cores ou ttk.Button padrão
        # Para simplificar e manter padrão sem bootstrap, vamos usar ttk.Button normal
        ttk.Button(actions, text="Adicionar Operação", command=self._add_trade).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Excluir Selecionada", command=self._delete_selected_trade).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

    def _month_title(self) -> str:
        month_name = [
            "",
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ][self.current_month]
        return f"{month_name} {self.current_year}"

    def _prev_month(self) -> None:
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._render_calendar()

    def _next_month(self) -> None:
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._render_calendar()

    def _day_total(self, d: date) -> float:
        # Recupera trades com segurança da estrutura nova
        trades_dict = self.data.get("trades", {})
        if not isinstance(trades_dict, dict):
            return 0.0
            
        items = trades_dict.get(_date_key(d), [])
        total = 0.0
        for t in items:
            try:
                total += float(t.get("pl", 0.0))
            except Exception:
                continue
        return total

    def _render_calendar(self) -> None:
        self.month_label.configure(text=self._month_title())

        cal = calendar.Calendar(firstweekday=0)
        month_days = list(cal.itermonthdates(self.current_year, self.current_month))

        def pad_to_6_weeks(days: List[date]) -> List[date]:
            from datetime import timedelta

            while len(days) < 42:
                days.append(days[-1] + timedelta(days=1))
            return days[:42]

        month_days = pad_to_6_weeks(month_days)

        for idx, d in enumerate(month_days):
            btn = self.day_buttons[idx]

            in_month = d.month == self.current_month
            total = self._day_total(d)

            total_text = ""
            if abs(total) > 1e-9:
                total_text = f"\n{total:+.2f}"

            btn.configure(
                text=f"{d.day}{total_text}",
                state=("normal" if in_month else "disabled"),
                command=lambda dd=d: self._select_date(dd),
            )

            # Estilização Padrão (Tkinter)
            if not in_month:
                btn.configure(state="disabled", bg="#f0f0f0") # Cinza claro para dias fora do mês
            else:
                if total > 0:
                    btn.configure(bg="#90ee90") # Light Green
                elif total < 0:
                    btn.configure(bg="#ffcccb") # Light Red
                else:
                    btn.configure(bg="SystemButtonFace") # Cor padrão do sistema

            if d == self.selected_date and in_month:
                 # Destacar dia selecionado (borda ou cor diferente)
                 # Como tk.Button tem limitações de borda no Windows, vamos mudar o fundo levemente
                 current_bg = btn.cget("bg")
                 if current_bg == "SystemButtonFace":
                     btn.configure(bg="#e0e0e0") # Cinza um pouco mais escuro
                 # Se já tem cor (verde/vermelho), mantemos a cor mas talvez alteremos o relevo
                 btn.configure(relief="sunken")
            else:
                 btn.configure(relief="flat")
            
        self._refresh_day_panel()

    def _select_date(self, d: date) -> None:
        self.selected_date = d
        if d.month != self.current_month or d.year != self.current_year:
            self.current_month = d.month
            self.current_year = d.year
        self._render_calendar()

    def _trades_for_selected_day(self) -> List[Dict[str, Any]]:
        # A chave de trades no self.data["trades"]
        if "trades" not in self.data:
            self.data["trades"] = {}
        return self.data["trades"].setdefault(_date_key(self.selected_date), [])
    
    def _get_trades_for_day(self, d: date) -> List[Dict[str, Any]]:
        if "trades" not in self.data:
            return []
        return self.data["trades"].get(_date_key(d), [])

    def _refresh_day_panel(self) -> None:
        if self.selected_date is None:
            return

        date_str = self.selected_date.strftime("%d/%m/%Y")
        self.selected_label.configure(text=f"Dia: {date_str}")

        # Atualizar lista de contas no combobox
        accounts = self.data.get("accounts", ["Padrão"])
        self.account_cb['values'] = accounts
        # Atualizar filtro de contas
        self.filter_account_cb['values'] = ["Todas"] + accounts

        all_trades = self._trades_for_selected_day()
        
        # Aplicar filtros
        f_asset = self.filter_asset_var.get()
        f_side = self.filter_side_var.get()
        f_account = self.filter_account_var.get()

        # Sincronizar seleção do formulário com o filtro, se específico
        if f_account != "Todas":
             self.account_var.set(f_account)
        elif not self.account_var.get():
             self.account_var.set(accounts[0])

        total_pl = 0.0
        wins = 0

        filtered_trades = []
        filtered_indices = [] # Para manter o índice original para exclusão
        
        # Coletar ativos únicos para o combobox
        unique_assets = set()
        for t in all_trades:
            unique_assets.add(t.get("asset", ""))

        # Atualizar combobox de ativos mantendo seleção se possível
        sorted_assets = sorted(list(unique_assets))
        self.filter_asset_cb['values'] = ["Todos"] + sorted_assets
        
        current_day_total = 0.0

        for i, t in enumerate(all_trades):
            if f_asset != "Todos" and t.get("asset") != f_asset:
                continue
            if f_side != "Todos" and t.get("side") != f_side:
                continue
            
            # Filtro de conta (compatibilidade com registros antigos sem conta)
            t_account = t.get("account", "Padrão")
            if f_account != "Todas" and t_account != f_account:
                continue

            filtered_trades.append(t)
            filtered_indices.append(i)
            try:
                current_day_total += float(t.get("pl", 0.0))
            except:
                pass

        # Limpar tabela
        for item in self.trades_tree.get_children():
            self.trades_tree.delete(item)

        # Preencher tabela
        for idx_in_filtered, t in enumerate(filtered_trades):
            original_idx = filtered_indices[idx_in_filtered]
            obs = t.get("obs", "")
            account = t.get("account", "Padrão")
            try:
                pl_val = float(t.get("pl", 0.0))
            except:
                pl_val = 0.0
            
            self.trades_tree.insert("", "end", iid=str(original_idx), values=(t.get("side"), t.get("asset"), f"{pl_val:+.2f}", obs, account))

        # Atualizar label de total
        total_day = self._day_total(self.selected_date)
        
        if f_asset == "Todos" and f_side == "Todos" and f_account == "Todas":
             self.day_total_label.configure(text=f"Total do dia: {total_day:+.2f}")
             color = "green" if total_day > 0 else "red" if total_day < 0 else "black"
        else:
             self.day_total_label.configure(text=f"Total (Filtrado): {current_day_total:+.2f}  |  Dia: {total_day:+.2f}")
             color = "green" if current_day_total > 0 else "red" if current_day_total < 0 else "black"
             
        self.day_total_label.configure(foreground=color)

    def _add_trade(self) -> None:
        side = self.side_var.get().strip()
        asset = self.asset_var.get().strip()
        pl_raw = self.pl_var.get()
        obs = self.obs_var.get().strip()
        account = self.account_var.get().strip()

        # Validações
        if side not in {"Compra", "Venda"}:
            messagebox.showerror("Erro", "Tipo inválido.")
            return
        if asset == "":
            messagebox.showerror("Erro", "Informe o ativo.")
            return
        if not account:
            messagebox.showerror("Erro", "Informe a conta.")
            return

        try:
            pl_val = _parse_pl(pl_raw)
        except Exception:
            messagebox.showerror("Erro", "Informe um valor válido para lucro/prejuízo.")
            return

        trades = self._trades_for_selected_day()
        trades.append({
            "side": side, 
            "asset": asset, 
            "pl": pl_val, 
            "obs": obs,
            "account": account
        })

        # Limpeza dos campos
        # self.asset_var.set("") # Mantém o ativo para facilitar inserção repetida
        self.pl_var.set("")
        self.obs_var.set("")
        
        self._save_data()
        self._render_calendar()

    def _manage_accounts(self) -> None:
        """Janela simples para adicionar/remover contas"""
        win = tk.Toplevel(self)
        win.title("Gerenciar Contas")
        win.geometry("300x400")
        
        lbl = ttk.Label(win, text="Contas cadastradas:", font=("Segoe UI", 10, "bold"))
        lbl.pack(pady=10)
        
        lst_frame = ttk.Frame(win)
        lst_frame.pack(fill="both", expand=True, padx=10)
        
        scrollbar = ttk.Scrollbar(lst_frame)
        scrollbar.pack(side="right", fill="y")
        
        lb = tk.Listbox(lst_frame, yscrollcommand=scrollbar.set)
        lb.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=lb.yview)
        
        for acc in self.data.get("accounts", []):
            lb.insert("end", acc)
            
        entry_var = tk.StringVar()
        entry = ttk.Entry(win, textvariable=entry_var)
        entry.pack(fill="x", padx=10, pady=5)
        
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def add_acc():
            name = entry_var.get().strip()
            if name and name not in self.data["accounts"]:
                self.data["accounts"].append(name)
                lb.insert("end", name)
                entry_var.set("")
                self._save_data()
                self._refresh_day_panel()
                
        def del_acc():
            sel = lb.curselection()
            if not sel: return
            idx = sel[0]
            val = lb.get(idx)
            if val == "Padrão":
                messagebox.showwarning("Aviso", "Não é possível remover a conta Padrão.")
                return
            if messagebox.askyesno("Confirmar", f"Excluir conta '{val}'?"):
                self.data["accounts"].remove(val)
                lb.delete(idx)
                self._save_data()
                self._refresh_day_panel()

        ttk.Button(btn_frame, text="Adicionar", command=add_acc).pack(side="left", fill="x", expand=True, padx=(0,5))
        ttk.Button(btn_frame, text="Remover", command=del_acc).pack(side="right", fill="x", expand=True, padx=(5,0))

    def _delete_selected_trade(self) -> None:
        selection = self.trades_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Selecione uma operação para excluir.")
            return
        try:
            idx = int(selection[0])
        except Exception:
            return

        trades = self._trades_for_selected_day()
        if 0 <= idx < len(trades):
            del trades[idx]
            # if not trades:
            #    self.data["trades"].pop(_date_key(self.selected_date), None)
            self._save_data()
            self._render_calendar()


def main() -> None:
    app = TradeJournalApp()
    app.mainloop()


if __name__ == "__main__":
    main()
