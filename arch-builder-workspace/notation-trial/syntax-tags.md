# 表記: タグ (`.html`)

```html
<diagram title="3層Web" icon-style="tile">          <!-- icon-style は省略可 -->
  <node id="users" icon="Users">利用者</node>
  <group id="cloud" kind="aws-cloud" layout="column">  <!-- layout: row (既定) / column / grid (cols="2") -->
    <node id="cf" icon="Amazon CloudFront">CloudFront</node>
    <group id="tokyo" kind="region" label="ap-northeast-1 (東京)">
      <node id="s3" icon="S3">S3<br>静的ファイル</node>   <!-- 改行は <br> -->
    </group>
  </group>
  <edge from="users" to="cf">HTTPS</edge>              <!-- 中身がラベル -->
  <edge from="cf" to="s3" dashed>OAC</edge>
  <edge from="a" to="b" arrow="both" exit="right" entry="left"></edge>
  <note>前提を 1 つ 1 行で</note>
</diagram>
```

- id は図全体で一意 (省略するとラベルかアイコン名から作られるが、線で指すなら書く)
- `<edge>` は `<diagram>` の中ならどこに書いてもよい
- 繰り返し (AZ ごと) も、すべて書き出す
