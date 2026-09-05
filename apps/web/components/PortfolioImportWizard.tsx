"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { allocationState, ImportedPosition, normalize, parseCsv, parseManual, PortfolioSnapshot } from "@/lib/portfolio-import";

const DEMO = "AAPL 20%\nMSFT 15%\nBTC 10%\nGLD 15%\nSPY 30%\nCASH:USD 10%";
const STEPS = ["Importer", "Vérifier", "Diagnostiquer", "Améliorer"];

function Stepper({ step }: { step: number }) {
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label="Progression de l'analyse">
      {STEPS.map((label, index) => (
        <li key={label} className={`rounded-xl border p-3 ${index <= step ? "border-cyan-500" : "border-border"}`}>
          <div className="text-[10px] mono text-muted">0{index + 1}</div>
          <div className="text-xs md:text-sm mt-1">{label}</div>
        </li>
      ))}
    </ol>
  );
}

function ImportStep({ onImport }: { onImport: (positions: ImportedPosition[]) => void }) {
  const [text, setText] = useState("");
  
  const readCsv = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) file.text().then((value) => onImport(parseCsv(value)));
  };

  return (
    <section className="card space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Importez vos positions</h2>
        <p className="text-xs text-muted mt-1">Les fichiers restent dans ce navigateur. Aucun ordre ne peut être envoyé depuis ce parcours.</p>
      </div>
      
      <textarea 
        value={text} 
        onChange={(event) => setText(event.target.value)} 
        rows={8} 
        placeholder={DEMO}
        className="w-full rounded-xl border border-border bg-surface p-3 mono text-sm" 
        aria-label="Positions avec poids" 
      />
      
      <div className="flex flex-wrap gap-2">
        <button 
          className="rounded-xl bg-cyan-600 text-white px-4 py-2 text-sm" 
          onClick={() => onImport(parseManual(text))} 
          disabled={!text.trim()}
        >
          Analyser la saisie
        </button>
        <label className="rounded-xl border border-border px-4 py-2 text-sm cursor-pointer">
          Importer un CSV
          <input className="sr-only" type="file" accept=".csv,text/csv" onChange={readCsv} />
        </label>
        <button 
          className="rounded-xl border border-border px-4 py-2 text-sm" 
          onClick={() => onImport(parseManual(DEMO, "demo"))}
        >
          Charger la démonstration
        </button>
      </div>
      <p className="text-xs text-muted2">Format : un symbole et un poids par ligne. OCR indisponible : aucun relevé n'est envoyé à un service externe.</p>
    </section>
  );
}

function PositionRow({ position, update, remove }: { position: ImportedPosition; update: (value: ImportedPosition) => void; remove: () => void }) {
  return (
    <tr className={position.excluded ? "opacity-50" : ""}>
      <td>{position.original}</td>
      <td>
        <input 
          className="w-24 bg-transparent border-b border-border mono" 
          value={position.ticker} 
          onChange={(event) => update({ ...position, ticker: event.target.value.toUpperCase(), status: "a_verifier" })} 
        />
      </td>
      <td>
        <div>{position.venue}</div>
        <div className="text-muted2">{position.currency}</div>
      </td>
      <td>
        <div>{position.instrumentType}</div>
        <div className="text-muted2">{position.exposureClass}</div>
      </td>
      <td>
        <input 
          type="number" 
          min="0" 
          step="0.01" 
          className="w-20 bg-transparent border-b border-border mono text-right" 
          value={position.weight ?? ""} 
          onChange={(event) => update({ ...position, weight: event.target.value === "" ? null : Number(event.target.value) })} 
        /> %
      </td>
      <td>
        <select 
          className="bg-surface border border-border rounded-lg p-1" 
          value={position.status} 
          onChange={(event) => update({ ...position, status: event.target.value as ImportedPosition["status"] })}
        >
          <option value="confirme">Confirmé</option>
          <option value="a_verifier">À vérifier</option>
          <option value="introuvable">Introuvable</option>
        </select>
      </td>
      <td className="whitespace-nowrap">
        <button 
          className="text-xs text-muted underline mr-2" 
          onClick={() => update({ ...position, excluded: !position.excluded })}
        >
          {position.excluded ? "Inclure" : "Exclure"}
        </button>
        <button className="text-xs text-red-500 underline" onClick={remove}>Supprimer</button>
      </td>
    </tr>
  );
}

function ConfirmStep({ positions, setPositions, onConfirm, back }: { positions: ImportedPosition[]; setPositions: (value: ImportedPosition[]) => void; onConfirm: () => void; back: () => void }) {
  const state = allocationState(positions);
  const update = (index: number, value: ImportedPosition) => setPositions(positions.map((position, i) => i === index ? value : position));

  return (
    <section className="card space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Confirmez chaque ligne</h2>
          <p className="text-xs text-muted">Le ticker seul n'est jamais une confirmation suffisante pour une correspondance inconnue.</p>
        </div>
        <strong className={`mono ${state.coherent ? "text-green-500" : "text-amber-500"}`}>
          {state.total.toFixed(2)} %
        </strong>
      </div>
      
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Entrée</th>
              <th>Instrument</th>
              <th>Place / devise</th>
              <th>Type / exposition</th>
              <th>Poids</th>
              <th>Statut</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((position, index) => (
              <PositionRow 
                key={position.id} 
                position={position} 
                update={(value) => update(index, value)} 
                remove={() => setPositions(positions.filter((_, i) => i !== index))} 
              />
            ))}
          </tbody>
        </table>
      </div>
      
      <div className="rounded-xl bg-surface3 p-3 text-xs">
        {state.missing > 0 && <p>⚠️ {state.missing} poids manquant(s) — aucune équipondération implicite.</p>}
        {state.ambiguous > 0 && <p>⚠️ {state.ambiguous} instrument(s) à confirmer ou exclure explicitement.</p>}
        {state.duplicates > 0 && <p>⚠️ {state.duplicates} doublon(s) potentiel(s), non fusionné(s).</p>}
        {Math.abs(state.total - 100) >= .01 && <p>⚠️ Total différent de 100 %. La normalisation est une action explicite.</p>}
      </div>
      
      <div className="flex flex-wrap gap-2">
        <button className="rounded-xl border border-border px-4 py-2 text-sm" onClick={back}>Retour</button>
        <button 
          className="rounded-xl border border-border px-4 py-2 text-sm" 
          onClick={() => setPositions(normalize(positions))} 
          disabled={state.total <= 0 || state.missing > 0}
        >
          Normaliser à 100 %
        </button>
        <button 
          className="rounded-xl bg-cyan-600 text-white px-4 py-2 text-sm disabled:opacity-40" 
          onClick={onConfirm} 
          disabled={!state.coherent}
        >
          Créer le snapshot
        </button>
      </div>
    </section>
  );
}

export function PortfolioImportWizard({ onSnapshot, initialSnapshot }: { onSnapshot?: (snapshot: PortfolioSnapshot | null) => void; initialSnapshot?: PortfolioSnapshot | null }) {
  const [step, setStep] = useState(0);
  const [positions, setPositions] = useState<ImportedPosition[]>([]);
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  
  const state = useMemo(() => allocationState(positions), [positions]);

  useEffect(() => { 
    if (initialSnapshot && !snapshot) { 
      setSnapshot(initialSnapshot); 
      setPositions(initialSnapshot.positions); 
      setStep(2); 
    } 
  }, [initialSnapshot, snapshot]);

  const importPositions = (value: ImportedPosition[]) => { 
    setPositions(value); 
    setSnapshot(null); 
    onSnapshot?.(null); 
    setStep(1); 
  };
  
  const confirm = () => { 
    const value = { 
      version: Date.now(), 
      createdAt: new Date().toISOString(), 
      baseCurrency: "USD", 
      positions: positions.filter((position) => !position.excluded) 
    }; 
    localStorage.setItem("portfolio-analysis-snapshot", JSON.stringify(value)); 
    setSnapshot(value); 
    onSnapshot?.(value); 
    setStep(2); 
  };

  return (
    <div className="space-y-5">
      <Stepper step={step} />
      
      {step === 0 && <ImportStep onImport={importPositions} />}
      
      {step === 1 && (
        <ConfirmStep 
          positions={positions} 
          setPositions={setPositions} 
          onConfirm={confirm} 
          back={() => setStep(0)} 
        />
      )}
      
      {step >= 2 && snapshot && (
        <section className="card space-y-4">
          <div className="eyebrow">Snapshot versionné</div>
          <h2 className="text-lg font-semibold">Portefeuille prêt pour le diagnostic quantitatif</h2>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div>
              <span className="text-muted">Positions</span>
              <div className="mono text-xl">{snapshot.positions.length}</div>
            </div>
            <div>
              <span className="text-muted">Couverture</span>
              <div className="mono text-xl">{state.total.toFixed(1)} %</div>
            </div>
            <div>
              <span className="text-muted">Devise</span>
              <div className="mono text-xl">{snapshot.baseCurrency}</div>
            </div>
            <div>
              <span className="text-muted">Version</span>
              <div className="mono text-xs mt-2">{snapshot.version}</div>
            </div>
          </div>
          
          <div className="rounded-xl bg-surface3 p-3 text-xs text-muted">
            Les métriques de marché restent <b>indisponibles</b> tant que les historiques ajustés et les taux FX réels ne sont pas chargés. Elles ne sont jamais remplacées par zéro. Ce snapshot n'est ni la performance réelle du compte, ni une instruction d'ordre.
          </div>
          
          <div className="flex gap-2">
            <button className="rounded-xl border border-border px-4 py-2 text-sm" onClick={() => setStep(1)}>
              Modifier
            </button>
            <button 
              className="rounded-xl bg-cyan-600 text-white px-4 py-2 text-sm" 
              onClick={() => {
                setStep(3);
                window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
              }}
            >
              Voir les scénarios
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
