import { useEffect, useMemo, useRef, useState } from "react";
import type { OperationGroupOption } from "../types/upload";
import type { DashboardFilters } from "../components/Dashboard2";

/**
 * DashboardFilterBar_v2
 * 严格对齐原软件 Dashboard2.tsx 中 DashboardFilterBar 的真实7筛选器+4按钮结构：
 *   筛选器：年份下拉 / 预算版本下拉 / 月份下拉 / 运营组下拉(联动店铺) / 店铺下拉 / 产品搜索框(datalist) / 数据视图下拉
 *   操作按钮：刷新 / 配置首页 / 导出当前视角 / AI分析(primary)
 * 保留 V2 的新配色(森林绿/琥珀金)、圆角、细边框视觉风格。
 */
export function DashboardFilterBar_v2({
  filters,
  groups,
  onChange,
  onRefresh,
  onExport,
  onAiOpen,
  onConfigure,
  productOptions = [],
}: {
  filters: DashboardFilters;
  groups: OperationGroupOption[];
  onChange: (filters: DashboardFilters) => void;
  onRefresh?: () => void;
  onExport?: () => void;
  onAiOpen?: () => void;
  onConfigure?: () => void;
  productOptions?: Array<{
    product_key?: string;
    product_code?: string | null;
    product_name: string;
  }>;
}) {
  const productFilterRef = useRef<HTMLDivElement>(null);
  const [productOpen, setProductOpen] = useState(false);
  const [activeProductIndex, setActiveProductIndex] = useState(0);
  const selectedGroup = groups.find(
    (group) => group.group_code === filters.group_code
  );
  const shops =
    selectedGroup?.shops || groups.flatMap((group) => group.shops || []);
  const filteredProducts = useMemo(() => {
    const current = filters.product_name.trim().toLocaleLowerCase();
    const hasExactMatch = productOptions.some(
      (item) => item.product_name.toLocaleLowerCase() === current
    );
    if (!current || hasExactMatch) return productOptions;
    return productOptions.filter((item) =>
      item.product_name.toLocaleLowerCase().includes(current)
    );
  }, [filters.product_name, productOptions]);

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!productFilterRef.current?.contains(event.target as Node)) {
        setProductOpen(false);
      }
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  useEffect(() => {
    setActiveProductIndex(0);
  }, [filters.product_name, productOpen]);

  function selectProduct(productName: string) {
    onChange({ ...filters, product_name: productName });
    setProductOpen(false);
  }

  function handleProductKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setProductOpen(false);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setProductOpen(true);
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setActiveProductIndex((index) => {
        if (!filteredProducts.length) return 0;
        return (index + direction + filteredProducts.length) % filteredProducts.length;
      });
      return;
    }
    if (event.key === "Enter" && productOpen && filteredProducts[activeProductIndex]) {
      event.preventDefault();
      selectProduct(filteredProducts[activeProductIndex].product_name);
    }
  }

  return (
    <div className="dashboard-filter-bar filter-bar">
      {/* ---------- 7 个筛选器 ---------- */}
      <label className="v2-filter-label-wrap">
        <span>年份</span>
        <select
          className="v2-filter-select"
          value={filters.year}
          onChange={(event) =>
            onChange({ ...filters, year: event.target.value })
          }
        >
          {[2026, 2027, 2028].map((year) => (
            <option key={year} value={year}>
              {year}年
            </option>
          ))}
        </select>
      </label>

      <label className="v2-filter-label-wrap">
        <span>预算版本</span>
        <select
          className="v2-filter-select"
          value={filters.budget_version}
          onChange={(event) =>
            onChange({ ...filters, budget_version: event.target.value })
          }
        >
          {[1, 2, 3, 4, 5].map((version) => (
            <option key={version} value={version}>
              第{version}版
            </option>
          ))}
        </select>
      </label>

      <label className="v2-filter-label-wrap">
        <span>月份</span>
        <select
          className="v2-filter-select"
          value={filters.month}
          onChange={(event) =>
            onChange({ ...filters, month: event.target.value })
          }
        >
          <option value="">全年(1-12月)</option>
          {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
            <option key={month} value={month}>
              {month}月
            </option>
          ))}
        </select>
      </label>

      <label className="v2-filter-label-wrap">
        <span>运营组</span>
        <select
          className="v2-filter-select"
          value={filters.group_code}
          onChange={(event) =>
            onChange({
              ...filters,
              group_code: event.target.value,
              shop_code: "",
            })
          }
        >
          <option value="">全部运营组</option>
          {groups.map((group) => (
            <option key={group.group_code} value={group.group_code}>
              {group.group_name}
            </option>
          ))}
        </select>
      </label>

      <label className="v2-filter-label-wrap">
        <span>店铺</span>
        <select
          className="v2-filter-select"
          value={filters.shop_code}
          onChange={(event) =>
            onChange({ ...filters, shop_code: event.target.value })
          }
        >
          <option value="">全部店铺</option>
          {shops.map((shop) => (
            <option key={shop.shop_code} value={shop.shop_code}>
              {shop.shop_name}
            </option>
          ))}
        </select>
      </label>

      <div className="v2-filter-label-wrap v2-product-filter" ref={productFilterRef}>
        <span>产品</span>
        <div className="v2-product-combobox">
          <input
            className="v2-filter-input"
            value={filters.product_name}
            onChange={(event) => {
              onChange({ ...filters, product_name: event.target.value });
              setProductOpen(true);
            }}
            onFocus={() => setProductOpen(true)}
            onKeyDown={handleProductKeyDown}
            placeholder="搜索或选择产品"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={productOpen}
            aria-controls="dashboard-product-options-v2"
          />
          <button
            type="button"
            className="v2-product-toggle"
            aria-label={productOpen ? "收起产品列表" : "展开产品列表"}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => setProductOpen((value) => !value)}
          >
            {productOpen ? "▲" : "▼"}
          </button>
          {productOpen && (
            <div className="v2-product-options" id="dashboard-product-options-v2" role="listbox">
              {filters.product_name && (
                <button
                  type="button"
                  className="v2-product-option clear-option"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectProduct("")}
                >
                  全部产品
                </button>
              )}
              {filteredProducts.map((item, index) => (
                <button
                  type="button"
                  className={`v2-product-option${index === activeProductIndex ? " active" : ""}`}
                  key={
                    item.product_key ||
                    `${item.product_code || "name"}-${item.product_name}-${index}`
                  }
                  role="option"
                  aria-selected={item.product_name === filters.product_name}
                  onMouseEnter={() => setActiveProductIndex(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectProduct(item.product_name)}
                >
                  {item.product_name}
                </button>
              ))}
              {!filteredProducts.length && <div className="v2-product-empty">未找到匹配产品</div>}
            </div>
          )}
        </div>
      </div>

      <label className="v2-filter-label-wrap">
        <span>数据视图</span>
        <select
          className="v2-filter-select primary-select"
          value={filters.data_view}
          onChange={(event) =>
            onChange({ ...filters, data_view: event.target.value })
          }
        >
          <option value="comparison">预算 vs 实际</option>
          <option value="budget">预算</option>
          <option value="actual">实际</option>
        </select>
      </label>

      {/* ---------- 4 个操作按钮 ---------- */}
      <div className="dashboard-actions v2-filter-actions">
        <button type="button" className="v2-action-btn" onClick={onRefresh}>
          刷新
        </button>
        <button
          type="button"
          className="v2-action-btn utility"
          onClick={onConfigure}
        >
          配置首页
        </button>
        <button
          type="button"
          className="v2-action-btn utility"
          onClick={onExport}
        >
          导出当前视角
        </button>
        <button
          type="button"
          className="v2-action-btn primary"
          onClick={onAiOpen}
        >
          AI分析
        </button>
      </div>
    </div>
  );
}

export default DashboardFilterBar_v2;
