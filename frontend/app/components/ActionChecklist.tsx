"use client";

import { useId, useMemo, useState } from "react";
import "./action-checklist.css";

export type ChecklistItem = {
  code: string;
  title: string;
  description: string;
  priority: string;
};

export type RecommendedAction = {
  label: string;
  description: string;
};

export type ActionChecklistProps = {
  checklist: ChecklistItem[];
  recommendedAction: RecommendedAction | null;
  resetKey?: string | number;
};

type PriorityTone = "high" | "medium" | "low" | "default";

const priorityLabels: Record<PriorityTone, string> = {
  high: "우선순위 높음",
  medium: "우선순위 중간",
  low: "우선순위 낮음",
  default: "우선순위 확인",
};

function getPriorityTone(priority: string): PriorityTone {
  const normalizedPriority = priority.trim().toLowerCase();

  if (normalizedPriority === "high") return "high";
  if (normalizedPriority === "medium") return "medium";
  if (normalizedPriority === "low") return "low";

  return "default";
}

function ActionChecklistContent({
  checklist,
  recommendedAction,
}: Omit<ActionChecklistProps, "resetKey">) {
  const sectionId = useId();
  const [completedItems, setCompletedItems] = useState<Set<string>>(
    () => new Set(),
  );

  const itemKeys = useMemo(
    () => checklist.map((item, index) => `${item.code}:${index}`),
    [checklist],
  );
  const completedCount = itemKeys.reduce(
    (count, itemKey) => count + (completedItems.has(itemKey) ? 1 : 0),
    0,
  );
  const progress = checklist.length
    ? Math.round((completedCount / checklist.length) * 100)
    : 0;

  function toggleItem(itemKey: string) {
    setCompletedItems((currentItems) => {
      const nextItems = new Set(currentItems);

      if (nextItems.has(itemKey)) {
        nextItems.delete(itemKey);
      } else {
        nextItems.add(itemKey);
      }

      return nextItems;
    });
  }

  return (
    <section
      className="action-checklist"
      id="action-checklist"
      aria-labelledby={`${sectionId}-title`}
    >
      <div className="action-checklist__container">
        <header className="action-checklist__heading">
          <p className="action-checklist__eyebrow">NEXT STEP · 행동 체크리스트</p>
          <h2 id={`${sectionId}-title`}>계약 전에 직접 확인할 일을 정리했어요</h2>
          <p>
            현재 분석 API가 제공한 항목입니다. 우선순위가 높은 항목부터 공식
            서류와 기관을 통해 확인해 주세요.
          </p>
        </header>

        {checklist.length === 0 ? (
          <div className="action-checklist__empty" role="status">
            <span aria-hidden="true">!</span>
            <div>
              <h3>제공된 행동 체크리스트가 없습니다</h3>
              <p>
                분석 API 응답에 체크리스트 항목이 포함되지 않았습니다. 잠시 후
                다시 분석하거나 응답 데이터를 확인해 주세요.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="action-checklist__progress-card">
              <div className="action-checklist__progress-copy">
                <span>확인 진행률</span>
                <strong aria-live="polite">
                  {completedCount}
                  <small> / {checklist.length}개</small>
                </strong>
              </div>
              <div className="action-checklist__progress-detail">
                <div
                  className="action-checklist__progress-track"
                  role="progressbar"
                  aria-label="행동 체크리스트 확인 진행률"
                  aria-valuemin={0}
                  aria-valuemax={checklist.length}
                  aria-valuenow={completedCount}
                  aria-valuetext={`${checklist.length}개 중 ${completedCount}개 확인`}
                >
                  <span style={{ width: `${progress}%` }} />
                </div>
                <p>{progress}% 확인 표시됨</p>
              </div>
            </div>

            <ol className="action-checklist__items">
              {checklist.map((item, index) => {
                const itemKey = itemKeys[index];
                const inputId = `${sectionId}-item-${index}`;
                const descriptionId = `${inputId}-description`;
                const priorityId = `${inputId}-priority`;
                const isCompleted = completedItems.has(itemKey);
                const priorityTone = getPriorityTone(item.priority);

                return (
                  <li
                    className={isCompleted ? "is-completed" : undefined}
                    key={itemKey}
                  >
                    <label
                      className="action-checklist__item"
                      htmlFor={inputId}
                    >
                      <input
                        checked={isCompleted}
                        className="action-checklist__checkbox"
                        id={inputId}
                        type="checkbox"
                        aria-describedby={`${descriptionId} ${priorityId}`}
                        onChange={() => toggleItem(itemKey)}
                      />
                      <span className="action-checklist__item-content">
                        <span className="action-checklist__item-meta">
                          <code>{item.code}</code>
                          <span
                            className={`action-checklist__priority action-checklist__priority--${priorityTone}`}
                            id={priorityId}
                          >
                            {priorityLabels[priorityTone]}
                          </span>
                        </span>
                        <strong>{item.title}</strong>
                        <span
                          className="action-checklist__description"
                          id={descriptionId}
                        >
                          {item.description}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ol>
          </>
        )}

        {recommendedAction ? (
          <article
            className="action-checklist__recommendation"
            aria-labelledby={`${sectionId}-recommendation-title`}
          >
            <span aria-hidden="true">→</span>
            <div>
              <p>분석 API 권장 행동</p>
              <h3 id={`${sectionId}-recommendation-title`}>
                {recommendedAction.label}
              </h3>
              <p>{recommendedAction.description}</p>
            </div>
          </article>
        ) : null}

        <aside className="action-checklist__notice" role="note">
          <strong>체크 표시는 공식 확인이 아닙니다.</strong>
          <p>
            완료 상태는 이 브라우저 화면의 메모리에만 임시로 유지됩니다.
            새로고침하거나 새 분석을 시작하면 초기화되며, 기관 확인이나 계약
            안전성을 증명하지 않습니다.
          </p>
        </aside>
      </div>
    </section>
  );
}

export function ActionChecklist({
  checklist,
  recommendedAction,
  resetKey,
}: ActionChecklistProps) {
  const fallbackResetKey = checklist
    .map(({ code }, index) => `${code}:${index}`)
    .join("|");

  return (
    <ActionChecklistContent
      key={resetKey ?? fallbackResetKey}
      checklist={checklist}
      recommendedAction={recommendedAction}
    />
  );
}
