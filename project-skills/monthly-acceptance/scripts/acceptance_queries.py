"""Deterministic read-only query plan. All aggregate cells, never a Top-N candidate scan."""
from acceptance_core import business_key, quoted, shift

KEYS = {
    'fingerprint': ['month_dt'], 'category': ['month_dt','path'],
    'bands': ['month_dt','path','band'], 'movement': ['month_dt','path'],
    'raw_paths': ['month_dt','path'], 'mapping': ['month_dt'],
    'sample': ['path','product_id'], 'release': ['release_id'],
}


def null_mismatch(left,right):
    return f'(({left} IS NULL AND {right} IS NOT NULL) OR ({left} IS NOT NULL AND {right} IS NULL))'


def path_expr(level):
    return "CAST('[]' AS STRING)" if level == 0 else 'CAST(JSON_ARRAY('+','.join('stdcategory'+str(i) for i in range(1,level+1))+') AS STRING)'


def where(m, site):
    return f"site={quoted(site)} AND month_dt BETWEEN {quoted(m['starts'][site]+'-01')} AND {quoted(m['data_month']+'-01')}"


def product_cte(m, site, level, entity='product_id'):
    return f"""p AS (SELECT month_dt,{path_expr(level)} AS path,NULLIF(TRIM({entity}),'') AS entity,
        SUM(discount_sales) AS amount,SUM(`count`) AS units,COUNT(1) AS nrows,
        SUM(CASE WHEN discount_sales IS NULL OR `count` IS NULL OR discount_sales<0 OR `count`<0 THEN 1 ELSE 0 END) AS invalid_rows
        FROM {m['policy']['std_table']} WHERE {where(m,site)}
        GROUP BY month_dt,path,entity)"""


def priced(m, site, level):
    return product_cte(m,site,level)+", v AS (SELECT *,CASE WHEN amount>0 AND units>0 AND invalid_rows=0 AND entity IS NOT NULL THEN amount/units END AS price FROM p)"


def band_expr(edges):
    return 'CASE WHEN price IS NULL THEN -1 '+''.join(f'WHEN price<{float(v)} THEN {i} ' for i,v in enumerate(edges))+f'ELSE {len(edges)} END'


def query(m, family, site, level=None, lag=None, entity=None, year=None, phase=None):
    pol=m['policy'];tbl=pol['std_table'];condition=where(m,site) if site in m['starts'] else ''
    if family=='release':
        return 'SELECT release_id,status,built_at,published_at,max_complete_month,scope_version,pipeline_version,source_wide_update_time,upstream_dim_update_time,source_derived_update_time,COUNT(1) OVER() AS total_rows FROM internal.flywheel_gov.gov_release'
    if family=='fingerprint':
        tbl=pol['raw_table'] if entity=='raw' else tbl
        return f"""SELECT month_dt,COUNT(1) AS nrows,COUNT(DISTINCT product_id) AS spus,
            SUM(`count`) AS units,SUM(discount_sales) AS amount,
            SUM(CASE WHEN product_id IS NULL OR TRIM(product_id)='' OR sku_id IS NULL OR month_dt IS NULL THEN 1 ELSE 0 END) AS invalid_keys,
            SUM(CASE WHEN discount_sales IS NULL OR `count` IS NULL OR discount_sales<0 OR `count`<0 THEN 1 ELSE 0 END) AS invalid_rows,
            COUNT(1) OVER() AS total_rows FROM {tbl} WHERE {condition} GROUP BY month_dt"""
    if family=='category':
        return f"""WITH {priced(m,site,level)} SELECT month_dt,path,COUNT(entity) AS spus,SUM(amount) AS amount,SUM(units) AS units,
            SUM(nrows) AS nrows,SUM(invalid_rows) AS invalid_rows,
            COUNT(price) AS priced_spus,SUM(CASE WHEN entity IS NULL THEN nrows ELSE 0 END) AS missing_product_rows,
            PERCENTILE_APPROX(price,0.1) AS p10,PERCENTILE_APPROX(price,0.5) AS p50,PERCENTILE_APPROX(price,0.9) AS p90,
            COUNT(1) OVER() AS total_rows FROM v GROUP BY month_dt,path"""
    if family=='bands':
        return f"""WITH {priced(m,site,level)} SELECT month_dt,path,{band_expr(pol['price_bands'][site])} AS band,
            COUNT(entity) AS spus,SUM(amount) AS amount,SUM(units) AS units,COUNT(1) OVER() AS total_rows
            FROM v GROUP BY month_dt,path,band"""
    if family=='raw_paths':
        return f"""SELECT month_dt,CAST(JSON_ARRAY(category_1,category_2,category_3,category_4,category_5,sub_category) AS STRING) AS path,
            COUNT(1) AS nrows,COUNT(DISTINCT product_id) AS spus,SUM(`count`) AS units,SUM(discount_sales) AS amount,
            COUNT(1) OVER() AS total_rows FROM {pol['raw_table']} WHERE {condition} GROUP BY month_dt,path"""
    if family=='movement':
        ident='product_id' if entity=='spu' else 'std_brand_name'
        begin=max(m['starts'][site],f'{year}-01');end=min(m['data_month'],f'{year}-12')
        # Absent sides describe observed entry/exit; they do not establish zero market sales.
        return f"""WITH {product_cte(m,site,level,ident)}, d AS (
            SELECT COALESCE(c.month_dt,CAST(DATE_ADD(CAST(b.month_dt AS DATE),INTERVAL {lag} MONTH) AS STRING)) AS month_dt,
            COALESCE(c.path,b.path) AS path,b.entity AS bentity,c.entity AS centity,
            b.nrows AS bn,c.nrows AS cn,COALESCE(b.amount,0) AS ba,COALESCE(c.amount,0) AS ca,
            COALESCE(b.units,0) AS bu,COALESCE(c.units,0) AS cu
            FROM p b FULL OUTER JOIN p c ON b.path=c.path AND b.entity <=> c.entity
            AND CAST(c.month_dt AS DATE)=DATE_ADD(CAST(b.month_dt AS DATE),INTERVAL {lag} MONTH))
            SELECT month_dt,path,COUNT(bn) AS base_entities,COUNT(cn) AS current_entities,
            SUM(CASE WHEN bn IS NULL THEN 1 ELSE 0 END) AS entered,SUM(CASE WHEN cn IS NULL THEN 1 ELSE 0 END) AS exited,
            SUM(ba) AS base_amount,SUM(ca) AS current_amount,SUM(bu) AS base_units,SUM(cu) AS current_units,
            SUM(GREATEST(ca-ba,0)) AS positive_amount,SUM(LEAST(ca-ba,0)) AS negative_amount,
            SUM(GREATEST(cu-bu,0)) AS positive_units,SUM(LEAST(cu-bu,0)) AS negative_units,
            COUNT(1) OVER() AS total_rows FROM d WHERE month_dt BETWEEN {quoted(begin+'-01')} AND {quoted(end+'-01')}
            GROUP BY month_dt,path"""
    if family=='mapping':
        begin=max(m['starts'][site],f'{year}-01');end=min(m['data_month'],f'{year}-12')
        cond=f"site={quoted(site)} AND month_dt BETWEEN {quoted(begin+'-01')} AND {quoted(end+'-01')}"
        keys='platform,site,month_dt,product_id,sku_id'
        agg=f'''SELECT {keys},COUNT(1) AS n,SUM(discount_sales) AS amount,SUM(`count`) AS units,
            SUM(CASE WHEN discount_sales IS NULL OR `count` IS NULL THEN 1 ELSE 0 END) AS null_values'''
        eq=' AND '.join(f'r.{k} <=> d.{k}' for k in keys.split(','))
        return f"""WITH r AS ({agg} FROM {pol['raw_table']} WHERE {cond} GROUP BY {keys}),
            d AS ({agg} FROM {tbl} WHERE {cond} GROUP BY {keys})
            SELECT COALESCE(r.month_dt,d.month_dt) AS month_dt,
            SUM(CASE WHEN r.n>1 THEN r.n-1 ELSE 0 END) AS raw_duplicate_rows,
            SUM(CASE WHEN d.n>1 THEN d.n-1 ELSE 0 END) AS std_duplicate_rows,
            SUM(CASE WHEN d.n IS NULL THEN 1 ELSE 0 END) AS raw_only_keys,
            SUM(CASE WHEN r.n IS NULL THEN 1 ELSE 0 END) AS std_only_keys,
            SUM(CASE WHEN r.n IS NOT NULL AND d.n IS NOT NULL THEN 1 ELSE 0 END) AS matched_keys,
            SUM(CASE WHEN r.n IS NOT NULL AND d.n IS NOT NULL AND (ABS(r.amount-d.amount)>{pol['amount_tolerance']} OR NOT (r.units <=> d.units) OR {null_mismatch('r.amount','d.amount')} OR r.null_values<>d.null_values) THEN 1 ELSE 0 END) AS value_mismatch_keys,
            COUNT(1) OVER() AS total_rows FROM r FULL OUTER JOIN d ON {eq} GROUP BY COALESCE(r.month_dt,d.month_dt)"""
    if family=='sample':
        n=int(pol['sample_per_category']);path=path_expr(3)
        title="COALESCE(NULLIF(TRIM(product_title),''),NULLIF(TRIM(product_title_cn),''),NULLIF(TRIM(sku_title),''))"
        raw_path='CAST(JSON_ARRAY(category_1,category_2,category_3,category_4,category_5,sub_category) AS STRING)'
        # Fixed seed + full category path + entity yields a reproducible stratified sample, independent of anomaly values.
        return f"""WITH s AS (SELECT {path} AS path,product_id,MAX({title}) AS title,MAX(std_brand_name) AS brand,
            MAX({raw_path}) AS raw_category,COUNT(DISTINCT {raw_path}) AS raw_path_count,
            COUNT(DISTINCT {title}) AS title_variants,MAX(product_url) AS product_url,COUNT(1) AS sku_rows,
            SUM(`count`) AS units,SUM(discount_sales) AS amount,
            MIN(discount_price) AS min_sku_price,MAX(discount_price) AS max_sku_price
            FROM {tbl} WHERE site={quoted(site)} AND month_dt={quoted(m['data_month']+'-01')} AND product_id IS NOT NULL
            GROUP BY path,product_id), ranked AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY path ORDER BY MD5(CONCAT({quoted(pol['sample_seed'])},path,product_id)),product_id) AS sample_rank FROM s)
            SELECT *,COUNT(1) OVER() AS total_rows FROM ranked WHERE sample_rank<={n}"""
    raise ValueError('未知查询族 '+family)


def job(m, family, site, **params):
    args={'family':family,'site':site,**params}
    return {**args,'job_id':business_key(args),'key_fields':KEYS[family], 'sql':query(m,**args)}


def plan(m, end_fingerprints=False):
    jobs=[] if end_fingerprints else [job(m,'release','global')]
    for site in m['sites']:
        for entity in ['raw','std']:
            jobs.append(job(m,'fingerprint',site,entity=entity,phase='end' if end_fingerprints else 'start'))
        if end_fingerprints:continue
        years=range(int(m['starts'][site][:4]),int(m['data_month'][:4])+1)
        jobs.append(job(m,'raw_paths',site))
        for year in years:jobs.append(job(m,'mapping',site,year=year))
        for level in m['policy']['levels']:
            jobs += [job(m,'category',site,level=level),job(m,'bands',site,level=level)]
            for lag in m['policy']['comparisons'].values():
                for year in years:
                    for entity in ['spu','brand']:
                        jobs.append(job(m,'movement',site,level=level,lag=lag,entity=entity,year=year))
        jobs.append(job(m,'sample',site))
    return jobs


def paginated(j, page_size, offset):
    return j['sql']+' ORDER BY '+','.join('`'+k+'`' for k in j['key_fields'])+f' LIMIT {page_size} OFFSET {offset}'


def drilldown(m, site, path, level, current, lag):
    """Full entity delta population for one cell; head/tail selection happens on complete local rows."""
    pth=path_expr(level);base=shift(current,-lag)
    return f"""WITH p AS (SELECT month_dt,product_id,MAX(product_title) AS title,MAX(std_brand_name) AS brand,
        MAX(sub_category) AS raw_category,MAX(product_url) AS product_url,COUNT(1) AS nrows,
        SUM(`count`) AS units,SUM(discount_sales) AS amount,MIN(discount_price) AS min_price,MAX(discount_price) AS max_price
        FROM {m['policy']['std_table']} WHERE site={quoted(site)} AND {pth}={quoted(path)}
        AND month_dt IN ({quoted(base+'-01')},{quoted(current+'-01')}) GROUP BY month_dt,product_id),
        b AS (SELECT * FROM p WHERE month_dt={quoted(base+'-01')}),c AS (SELECT * FROM p WHERE month_dt={quoted(current+'-01')})
        SELECT COALESCE(b.product_id,c.product_id) AS product_id,COALESCE(c.title,b.title) AS title,COALESCE(c.brand,b.brand) AS brand,
        b.raw_category AS base_category,c.raw_category AS current_category,COALESCE(c.product_url,b.product_url) AS product_url,
        b.nrows AS base_rows,c.nrows AS current_rows,b.units AS base_units,c.units AS current_units,b.amount AS base_amount,c.amount AS current_amount,
        b.min_price AS base_min_price,b.max_price AS base_max_price,c.min_price AS current_min_price,c.max_price AS current_max_price,
        COUNT(1) OVER() AS total_rows FROM b FULL OUTER JOIN c ON b.product_id <=> c.product_id"""
