/* 校园集市 · 交互脚本 */
document.addEventListener('DOMContentLoaded', function () {
  // 演示账号一键填充
  document.querySelectorAll('.demo-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var u = document.getElementById('username');
      var p = document.getElementById('password');
      if (u && p) {
        u.value = chip.dataset.user || '';
        p.value = chip.dataset.pass || '';
        p.focus();
        chip.style.borderColor = '#f2612b';
        setTimeout(function () { chip.style.borderColor = ''; }, 700);
      }
    });
  });

  // 发布页图片预览
  var fileInput = document.getElementById('image');
  var preview = document.getElementById('preview');
  var placeholder = document.getElementById('uploadPlaceholder');
  if (fileInput && preview) {
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (file.size > 8 * 1024 * 1024) {
        alert('图片超过 8MB，请压缩后再上传');
        fileInput.value = '';
        return;
      }
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
      if (placeholder) placeholder.hidden = true;
    });
  }

  // 提示条自动消失
  document.querySelectorAll('.flash').forEach(function (el, i) {
    setTimeout(function () {
      el.style.transition = 'opacity .4s, transform .4s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-6px)';
      setTimeout(function () { el.remove(); }, 420);
    }, 5000 + i * 300);
  });
});
