// oa_payment_form_template.typ
// 1. 引入 sys 模块以访问通过 --input 传入的外部参数。
#import sys
// 2. 从 sys.inputs 中获取名为 "data" 的 JSON 字符串，并将其解码为 Typst 字典。
#let data = json.decode(sys.inputs.data)

// ====================================================================
// 【优化内容】将结构化数据嵌入到 PDF 的 keywords 元信息中
// ====================================================================
// 3. 准备要嵌入的自定义数据字符串
#let serialized_data = json.encode(data)
#let data_keyword = "app-data-json:" + serialized_data

// 4. 设置文档元信息，仅修改 keywords 部分
#set document(
  title: "OA报销付款申请单",                 // 保持不变
  author: "zhengyouxin@cpe-fund.com",      // 保持不变
  date: auto,                              // 保持不变
  keywords: (                              // 数据写入meta信息
    data.at("order_id", default: ""),      // 添加一些关键字段作为普通关键词
    data.at("oa_no", default: ""),
    data_keyword                           // 嵌入完整的、带前缀的JSON数据
  ),
)
// ====================================================================

#import "@preview/tablex:0.0.9": tablex, cellx, colspanx

// 辅助函数
// 下划线
#let fulluline(content) = {
  box(
    width: 1fr,
    stroke: (bottom: 0.5pt),
    inset: (bottom: 2pt),
    content
  )
}

//单元格里的下划线
#let colline(content) = {
  box(
    width: 50%,
    stack(
      dir: ltr,
      box(stroke: (bottom: 0.5pt), width: 100%, height: 1em, content),
    )
  )
}

// 选项框
#let checkbox(checked) = {
  if checked {
    text(font: "DejaVu Sans", size: 10pt)[☑]
  } else {
    text(font: "DejaVu Sans", size: 10pt)[☐]
  }
}

// 页面设置
#set page(
  paper: "a4",
  margin: (top: 1in, right: 15mm, left: 15mm, bottom: 1in),
)

#set text(
  font: ("Arial", "Microsoft YaHei"),
  size: 9pt,
  lang: "zh",
)

// 标题
#align(center)[
  #text(size: 12pt, weight: "bold")[
    PAYMENT REQUESTS FORM \
    付款申请单
  ]
]

#v(8mm)

// 基本信息
#grid(
  columns: (auto, 1fr, auto, 20%),
  column-gutter: 10pt,
  row-gutter: 3mm,

  [COMPANY 公司:], fulluline(text(weight: "bold")[#data.payer]),
  [PRF No. 申请单编号:], fulluline(text(weight: "bold")[#data.order_id]),

  [DEPARTMENT 部门:], fulluline(text(weight: "bold")[#data.department]),
  [DATE 日期:], fulluline(text(weight: "bold")[#data.prf_date]),

  [PROJECT 项目:], fulluline(text(weight: "bold")[#data.project_name]),
  [PROJECT CODE 项号:], fulluline(text(weight: "bold")[#data.project_code]),
)

#v(5mm)

// 付款明细
#text(size: 9pt)[DETAILS OF PAYMENT 付款明细]

#tablex(
  columns: (60%, 1fr, 1fr),
  align: left + top,
  stroke: 0.5pt,
  inset: 10pt,

  [Name of Payee 收款人姓名: \ #text(weight: "bold")[#data.payee]],
  [Currency 货币: \ #text(weight: "bold")[#data.currency]],
  [Amount 金额: \ #text(weight: "bold")[#data.amount]],

  [
    Payment Reason 付款理由: \
    #v(1fr)
    #text(weight: "bold")[#data.payment_reason] \
    #v(1fr)
  ],
  colspanx(2)[
    Payment Method 付款方式: \
    #v(2em)
    #grid(
      columns: (auto, 1fr),
      row-gutter: 16pt,
      column-gutter: 30pt,

      // 第一行：标题行
      [],
      align(left)[#text(size: 7pt, style: "italic")[DBS Cheque No.]],

      // 第二行：Cheque选项
      [#checkbox(data.bank_settled == "Cheque") Cheque 支票],
      colline(
          if data.bank_settled == "Cheque" {
            text(size: 7pt, style: "italic")[#data.at("cheque_no", default: "")]
          }
      ),

      // 第三行： Online选项
      [#checkbox(data.bank_settled == "Online") Online 网上],
      [],

      // 第四行： FPS Payment
      [#checkbox(data.bank_settled == "FPS Payment") FPS Payment],
      [],

      // 第五行： Others选项
      [#checkbox(data.bank_settled == "Others") Others 其它],
      colline([]),
    ) \
    #v(1em)
  ],

  [
    Supporting Document Attached 附上支持文件: \
    #if data.attachments.len() > 0 [
      #for attachment in data.attachments [
        #text(weight: "bold", size: 8pt)[#attachment] \
      ]
    ] else [
      #text(style: "italic", size: 7pt, fill: gray)[无附件 / No attachments]
    ]
  ],
  colspanx(2)[
    Payment Date 付款日期： \
    #text(weight: "bold")[#data.prf_date]
  ],
)

#v(5mm)

// 审批表格标题
#text(size: 9pt)[APPROVAL 审批]

// 审批表格
#table(
  columns: (1fr, 1fr, 1fr, 1fr, 1fr),
  stroke: 0.5pt,
  inset: 8pt,
  align: center,

   // 第一行：标题
  [Initiator \ 经办人],
  [Reviewed By \ 财务审阅],
  [Department \ 部门负责人],
  [Finance \ 财务负责人],
  [Group CFO \ 首席财务官],

  // 第二行：签名区域（空白，保留边框）
  table.cell(stroke: (top: none, bottom: none, left: 0.5pt, right: 0.5pt), fill: none, inset: (top: 15pt))[#image("images/sign.png", height: 40pt, fit: "cover")],
  table.cell(stroke: (top: none, bottom: none, left: 0.5pt, right: 0.5pt), fill: none, inset: (top: 45pt))[],
  table.cell(stroke: (top: none, bottom: none, left: 0.5pt, right: 0.5pt), fill: none, inset: (top: 45pt))[],
  table.cell(stroke: (top: none, bottom: none, left: 0.5pt, right: 0.5pt), fill: none, inset: (top: 45pt))[],
  table.cell(stroke: (top: none, bottom: none, left: 0.5pt, right: 0.5pt), fill: none, inset: (top: 45pt))[],

  // 第三行：日期（顶部无边框）
  table.cell(
    align: left,
    stroke: (top: none, bottom: 0.5pt, left: 0.5pt, right: 0.5pt),
    [#text(size: 7pt)[Date 日期：#datetime.today().display("[year]-[month]-[day]")]]
  ),
  table.cell(
    align: left,
    stroke: (top: none, bottom: 0.5pt, left: 0.5pt, right: 0.5pt),
    [#text(size: 7pt)[Date 日期：]]
  ),
  table.cell(
    align: left,
    stroke: (top: none, bottom: 0.5pt, left: 0.5pt, right: 0.5pt),
    [#text(size: 7pt)[Date 日期：]]
  ),
  table.cell(
    align: left,
    stroke: (top: none, bottom: 0.5pt, left: 0.5pt, right: 0.5pt),
    [#text(size: 7pt)[Date 日期：]]
  ),
  table.cell(
    align: left,
    stroke: (top: none, bottom: 0.5pt, left: 0.5pt, right: 0.5pt),
    [#text(size: 7pt)[Date 日期：]]
  ),
)

#v(5mm)

// OA申请单号
#text(size: 9pt)[OA申请单号]

#tablex(
  columns: (20%, 1fr),
  align: left,
  stroke: 0.5pt,
  inset: 8pt,

  [OA申请单号:],
  link(data.oa_url)[#text(fill: blue)[#data.oa_no]],
)
